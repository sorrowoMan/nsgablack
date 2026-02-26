from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, Mapping, Optional, Tuple

import numpy as np
from scipy import optimize

from ..base import Plugin
from ...utils.constraints.constraint_utils import evaluate_constraints_safe
from ...utils.context.context_keys import (
    KEY_METRICS,
    KEY_METRICS_IMPLICIT_ITERS,
    KEY_METRICS_IMPLICIT_RESIDUAL,
    KEY_METRICS_IMPLICIT_SUCCESS,
)
from ...utils.context.context_schema import build_minimal_context
from ...utils.extension_contracts import (
    normalize_bias_output,
    normalize_candidate,
    normalize_objectives,
    normalize_violation,
)


ResidualFn = Callable[[np.ndarray], np.ndarray]
JacobianFn = Callable[[np.ndarray], np.ndarray]


@dataclass
class NumericalSolveResult:
    solution: np.ndarray
    residual_norm: float
    iterations: int
    success: bool
    method: str
    message: str = ""


@dataclass
class NumericalSolverConfig:
    tol: float = 1e-8
    max_iter: int = 100
    fallback_to_problem_eval: bool = True
    warn_on_failure: bool = True


class NumericalSolverPlugin(Plugin):
    """Base plugin for implicit-equation numerical solving."""

    is_algorithmic = True
    context_requires = ("problem",)
    context_provides = (
        KEY_METRICS_IMPLICIT_RESIDUAL,
        KEY_METRICS_IMPLICIT_ITERS,
        KEY_METRICS_IMPLICIT_SUCCESS,
    )
    context_mutates = (KEY_METRICS,)
    context_cache = ()
    context_notes = (
        "Short-circuits evaluate_individual when problem defines "
        "build_implicit_system(...) and evaluate_from_implicit_solution(...).",
    )

    def __init__(
        self,
        name: str = "numerical_solver",
        *,
        config: Optional[NumericalSolverConfig] = None,
        priority: int = 50,
    ) -> None:
        super().__init__(name=name, priority=priority)
        self.cfg = config or NumericalSolverConfig()
        self.stats: Dict[str, float] = {
            "calls": 0.0,
            "success": 0.0,
            "failure": 0.0,
            "fallback": 0.0,
            "last_residual": 0.0,
            "last_iterations": 0.0,
        }

    def solve_backend(
        self,
        residual: ResidualFn,
        x0: np.ndarray,
        jacobian: Optional[JacobianFn] = None,
    ) -> NumericalSolveResult:
        kwargs: Dict[str, Any] = {"tol": float(self.cfg.tol)}
        if jacobian is not None:
            kwargs["jac"] = jacobian
        out = optimize.root(
            residual,
            np.asarray(x0, dtype=float).reshape(-1),
            method="hybr",
            options={"maxfev": int(self.cfg.max_iter)},
            **kwargs,
        )
        solution = np.asarray(out.x, dtype=float).reshape(-1)
        residual_val = np.asarray(residual(solution), dtype=float).reshape(-1)
        return NumericalSolveResult(
            solution=solution,
            residual_norm=float(np.linalg.norm(residual_val)),
            iterations=int(getattr(out, "nfev", 0)),
            success=bool(getattr(out, "success", False)),
            method="root_hybr",
            message=str(getattr(out, "message", "")),
        )

    def _extract_system(
        self,
        problem: Any,
        x: np.ndarray,
        eval_context: Dict[str, Any],
    ) -> Optional[Tuple[ResidualFn, np.ndarray, Optional[JacobianFn]]]:
        builder = getattr(problem, "build_implicit_system", None)
        if not callable(builder):
            return None
        payload = builder(x, eval_context)
        if not isinstance(payload, Mapping):
            return None
        residual = payload.get("residual")
        if not callable(residual):
            return None
        x0 = payload.get("x0", np.zeros(1, dtype=float))
        jac = payload.get("jacobian")
        x0_arr = np.asarray(x0, dtype=float).reshape(-1)
        jac_fn = jac if callable(jac) else None
        return residual, x0_arr, jac_fn

    def _compute_violation(
        self,
        problem: Any,
        x: np.ndarray,
        solution: np.ndarray,
        eval_context: Dict[str, Any],
    ) -> Tuple[np.ndarray, float]:
        cons_from_implicit = getattr(problem, "evaluate_constraints_from_implicit_solution", None)
        if callable(cons_from_implicit):
            cons_arr = np.asarray(cons_from_implicit(x, solution, eval_context), dtype=float).reshape(-1)
            violation = float(np.sum(np.maximum(cons_arr, 0.0)))
            return cons_arr, violation
        cons_arr, violation = evaluate_constraints_safe(problem, x)
        return cons_arr, float(violation)

    def _apply_bias(
        self,
        solver: Any,
        x: np.ndarray,
        obj: np.ndarray,
        individual_id: Optional[int],
        context: Dict[str, Any],
    ) -> np.ndarray:
        if not bool(getattr(solver, "enable_bias", False)):
            return obj
        bias_module = getattr(solver, "bias_module", None)
        if bias_module is None:
            return obj
        if callable(getattr(bias_module, "compute_bias_vector", None)):
            return np.asarray(
                bias_module.compute_bias_vector(x, obj, individual_id, context=context),
                dtype=float,
            ).reshape(-1)
        if callable(getattr(bias_module, "compute_bias", None)):
            if obj.size == 1:
                val = normalize_bias_output(
                    bias_module.compute_bias(x, float(obj[0]), individual_id, context=context),
                    name="bias.compute_bias",
                )
                return np.array([val], dtype=float)
            out = []
            for idx in range(obj.size):
                val = normalize_bias_output(
                    bias_module.compute_bias(x, float(obj[idx]), individual_id, context=context),
                    name="bias.compute_bias",
                )
                out.append(val)
            return np.asarray(out, dtype=float)
        return obj

    def evaluate_individual(self, solver, x: np.ndarray, individual_id: Optional[int] = None):
        problem = getattr(solver, "problem", None)
        if problem is None:
            return None
        eval_from_implicit = getattr(problem, "evaluate_from_implicit_solution", None)
        if not callable(eval_from_implicit):
            return None

        x_arr = normalize_candidate(x, dimension=int(getattr(solver, "dimension", len(np.asarray(x)))), name="implicit.x")
        eval_context: Dict[str, Any] = {
            "solver": solver,
            "generation": int(getattr(solver, "generation", 0)),
            "individual_id": 0 if individual_id is None else int(individual_id),
        }
        extracted = self._extract_system(problem, x_arr, eval_context)
        if extracted is None:
            return None
        residual, x0, jacobian = extracted

        self.stats["calls"] += 1.0
        try:
            result = self.solve_backend(residual=residual, x0=x0, jacobian=jacobian)
        except Exception as exc:
            self.stats["failure"] += 1.0
            if not self.cfg.fallback_to_problem_eval:
                raise
            if self.cfg.warn_on_failure:
                print(f"[implicit-backend:{self.name}] solve failed, fallback to problem.evaluate: {exc}")
            self.stats["fallback"] += 1.0
            value = problem.evaluate(x_arr)
            obj = normalize_objectives(value, num_objectives=int(getattr(solver, "num_objectives", 1)), name="problem.evaluate")
            cons, violation = evaluate_constraints_safe(problem, x_arr)
            context = build_minimal_context(
                generation=int(getattr(solver, "generation", 0)),
                individual_id=eval_context["individual_id"],
                constraints=cons.tolist() if np.asarray(cons).size > 0 else [],
                constraint_violation=float(violation),
                extra={"problem": problem},
            )
            obj = self._apply_bias(solver, x_arr, obj, individual_id, context)
            return obj, normalize_violation(violation, name="constraint_violation")

        if result.success:
            self.stats["success"] += 1.0
        else:
            self.stats["failure"] += 1.0
        self.stats["last_residual"] = float(result.residual_norm)
        self.stats["last_iterations"] = float(result.iterations)

        raw_obj = eval_from_implicit(x_arr, result.solution, eval_context)
        obj = normalize_objectives(
            raw_obj,
            num_objectives=int(getattr(solver, "num_objectives", 1)),
            name="implicit.evaluate_from_solution",
        )
        cons_arr, violation = self._compute_violation(problem, x_arr, result.solution, eval_context)
        violation = normalize_violation(violation, name="constraint_violation")

        context = build_minimal_context(
            generation=int(getattr(solver, "generation", 0)),
            individual_id=eval_context["individual_id"],
            constraints=cons_arr.tolist() if np.asarray(cons_arr).size > 0 else [],
            constraint_violation=violation,
            extra={"problem": problem},
        )
        metrics = context.get(KEY_METRICS)
        if not isinstance(metrics, dict):
            metrics = {}
            context[KEY_METRICS] = metrics
        metrics[KEY_METRICS_IMPLICIT_RESIDUAL.split(".", 1)[1]] = float(result.residual_norm)
        metrics[KEY_METRICS_IMPLICIT_ITERS.split(".", 1)[1]] = float(result.iterations)
        metrics[KEY_METRICS_IMPLICIT_SUCCESS.split(".", 1)[1]] = 1.0 if result.success else 0.0

        obj = self._apply_bias(solver, x_arr, obj, individual_id, context)
        if bool(getattr(solver, "ignore_constraint_violation_when_bias", False)) and bool(
            getattr(solver, "enable_bias", False)
        ):
            violation = 0.0
        return obj, float(violation)

    def get_report(self) -> Optional[Dict[str, Any]]:
        out = super().get_report() or {}
        out["stats"] = dict(self.stats)
        return out

