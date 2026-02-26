from __future__ import annotations

from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
import time
from typing import Any, Callable, Dict, Mapping, Optional, Tuple

import numpy as np

from ..base import Plugin
from ...utils.context.context_keys import (
    KEY_METRICS,
    KEY_METRICS_INNER_CALLS,
    KEY_METRICS_INNER_ELAPSED_MS,
    KEY_METRICS_INNER_STATUS,
)
from ...utils.context.context_schema import build_minimal_context
from ...utils.extension_contracts import normalize_bias_output, normalize_objectives, normalize_violation
from .backend_contract import BackendSolveRequest, normalize_backend_output


InnerProblemFactory = Callable[[np.ndarray, Dict[str, Any]], Any]
InnerSolverFactory = Callable[[Any, Dict[str, Any]], Any]
InnerRunner = Callable[[Any, Any, Dict[str, Any]], Mapping[str, Any]]
InnerBackendFactory = Callable[[Any, Dict[str, Any]], Any]


@dataclass
class InnerSolverConfig:
    source_layer: str = "L2"
    target_layer: str = "L1"
    fallback_penalty: float = 1e6
    warn_on_failure: bool = True
    per_call_timeout_ms: Optional[int] = None
    max_retries: int = 0
    retry_backoff_ms: float = 0.0


class InnerSolverPlugin(Plugin):
    """Run an inner evaluation workflow and expose only mapped result to outer solver."""

    is_algorithmic = True
    context_requires = ("problem",)
    context_provides = (KEY_METRICS_INNER_ELAPSED_MS, KEY_METRICS_INNER_STATUS, KEY_METRICS_INNER_CALLS)
    context_mutates = (KEY_METRICS,)
    context_cache = ()
    context_notes = (
        "Short-circuits evaluate_individual via inner workflow; "
        "broadcasts packet through on_inner_result for bridge plugins.",
    )

    def __init__(
        self,
        name: str = "inner_solver",
        *,
        config: Optional[InnerSolverConfig] = None,
        inner_problem_factory: Optional[InnerProblemFactory] = None,
        inner_solver_factory: Optional[InnerSolverFactory] = None,
        inner_backend_factory: Optional[InnerBackendFactory] = None,
        inner_runner: Optional[InnerRunner] = None,
        priority: int = 70,
    ) -> None:
        super().__init__(name=name, priority=priority)
        self.cfg = config or InnerSolverConfig()
        self.inner_problem_factory = inner_problem_factory
        self.inner_solver_factory = inner_solver_factory
        self.inner_backend_factory = inner_backend_factory
        self.inner_runner = inner_runner
        self.stats: Dict[str, float] = {
            "calls": 0.0,
            "success": 0.0,
            "failure": 0.0,
            "blocked": 0.0,
            "fallback": 0.0,
            "retries": 0.0,
            "timeouts": 0.0,
            "last_elapsed_ms": 0.0,
        }

    def _build_task(self, problem: Any, x: np.ndarray, eval_ctx: Dict[str, Any]) -> Dict[str, Any]:
        task: Dict[str, Any] = {}

        if callable(self.inner_problem_factory):
            task["inner_problem"] = self.inner_problem_factory(x, eval_ctx)
        else:
            hook = getattr(problem, "build_inner_problem", None)
            if callable(hook):
                task["inner_problem"] = hook(x, eval_ctx)

        if "inner_problem" in task:
            if callable(self.inner_solver_factory):
                task["inner_solver"] = self.inner_solver_factory(task["inner_problem"], eval_ctx)
            else:
                hook = getattr(problem, "build_inner_solver", None)
                if callable(hook):
                    task["inner_solver"] = hook(task["inner_problem"], eval_ctx)
            if callable(self.inner_backend_factory):
                task["inner_backend"] = self.inner_backend_factory(task["inner_problem"], eval_ctx)
            else:
                hook = getattr(problem, "build_inner_backend", None)
                if callable(hook):
                    task["inner_backend"] = hook(task["inner_problem"], eval_ctx)

        if callable(self.inner_runner):
            task["run_inner"] = self.inner_runner
        else:
            run_hook = getattr(problem, "run_inner_solver", None)
            if callable(run_hook):
                task["run_inner"] = lambda p, s, c: run_hook(p, s, c)

        direct = getattr(problem, "build_inner_task", None)
        if callable(direct):
            payload = direct(x, eval_ctx)
            if isinstance(payload, Mapping):
                task.update(dict(payload))
        return task

    def _run_task(self, task: Dict[str, Any], eval_ctx: Dict[str, Any]) -> Dict[str, Any]:
        evaluator = task.get("evaluation_model")
        if evaluator is None:
            pm = getattr(self.solver, "plugin_manager", None) if self.solver is not None else None
            if pm is not None and hasattr(pm, "list_plugins"):
                for plugin in pm.list_plugins(enabled_only=True):
                    if callable(getattr(plugin, "evaluate_model", None)) and bool(getattr(plugin, "allow_inner", False)):
                        evaluator = plugin
                        break
        if evaluator is not None and callable(getattr(evaluator, "evaluate_model", None)):
            request = BackendSolveRequest(
                candidate=np.asarray(eval_ctx.get("candidate"), dtype=float).reshape(-1),
                eval_context=dict(eval_ctx),
                inner_problem=task.get("inner_problem"),
                inner_solver=task.get("inner_solver"),
                payload=dict(task),
            )
            raw = evaluator.evaluate_model(self.solver, request)
            if not isinstance(raw, Mapping):
                raise TypeError("evaluation_model.evaluate_model() must return mapping")
            return normalize_backend_output(raw)

        backend = task.get("inner_backend")
        if backend is not None and callable(getattr(backend, "solve", None)):
            request = BackendSolveRequest(
                candidate=np.asarray(eval_ctx.get("candidate"), dtype=float).reshape(-1),
                eval_context=dict(eval_ctx),
                inner_problem=task.get("inner_problem"),
                inner_solver=task.get("inner_solver"),
                payload=dict(task),
            )
            raw = backend.solve(request)
            if not isinstance(raw, Mapping):
                raise TypeError("inner backend solve() must return mapping")
            return normalize_backend_output(raw)

        run_inner = task.get("run_inner")
        if callable(run_inner):
            out = run_inner(task.get("inner_problem"), task.get("inner_solver"), eval_ctx)
            if isinstance(out, Mapping):
                return dict(out)
            raise TypeError("run_inner must return mapping")

        inner_solver = task.get("inner_solver")
        if inner_solver is None or not callable(getattr(inner_solver, "run", None)):
            raise RuntimeError("inner solver is not runnable")
        max_steps = task.get("max_steps")
        if max_steps is None:
            raw = inner_solver.run()
        else:
            raw = inner_solver.run(max_steps=int(max_steps))
        if isinstance(raw, Mapping):
            return dict(raw)
        return {"status": "completed", "raw": raw}

    def _run_task_with_timeout(self, task: Dict[str, Any], eval_ctx: Dict[str, Any]) -> Dict[str, Any]:
        timeout_ms = self.cfg.per_call_timeout_ms
        if timeout_ms is None or float(timeout_ms) <= 0:
            return self._run_task(task, eval_ctx)
        timeout_s = float(timeout_ms) / 1000.0
        with ThreadPoolExecutor(max_workers=1) as pool:
            fut = pool.submit(self._run_task, task, eval_ctx)
            try:
                return fut.result(timeout=timeout_s)
            except FutureTimeoutError as exc:
                self.stats["timeouts"] += 1.0
                raise TimeoutError(f"inner task timeout after {timeout_ms} ms") from exc

    def _fallback(self, solver: Any) -> Tuple[np.ndarray, float]:
        n_obj = int(getattr(solver, "num_objectives", 1))
        penalty = float(self.cfg.fallback_penalty)
        return np.full((n_obj,), penalty, dtype=float), penalty

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
        vector_hook = getattr(bias_module, "compute_bias_vector", None)
        if callable(vector_hook):
            return np.asarray(vector_hook(x, obj, individual_id, context=context), dtype=float).reshape(-1)
        scalar_hook = getattr(bias_module, "compute_bias", None)
        if callable(scalar_hook):
            if obj.size == 1:
                val = normalize_bias_output(
                    scalar_hook(x, float(obj[0]), individual_id, context=context),
                    name="bias.compute_bias",
                )
                return np.array([val], dtype=float)
            out = []
            for idx in range(obj.size):
                val = normalize_bias_output(
                    scalar_hook(x, float(obj[idx]), individual_id, context=context),
                    name="bias.compute_bias",
                )
                out.append(val)
            return np.asarray(out, dtype=float)
        return obj

    def evaluate_individual(self, solver, x: np.ndarray, individual_id: Optional[int] = None):
        problem = getattr(solver, "problem", None)
        if problem is None:
            return None

        x_arr = np.asarray(x, dtype=float).reshape(-1)
        eval_ctx: Dict[str, Any] = {
            "solver": solver,
            "candidate": x_arr,
            "individual_id": 0 if individual_id is None else int(individual_id),
            "generation": int(getattr(solver, "generation", 0)),
            "scope": "inner",
            "source_layer": self.cfg.source_layer,
            "target_layer": self.cfg.target_layer,
        }
        task = self._build_task(problem, x_arr, eval_ctx)
        if not task:
            return None

        self.stats["calls"] += 1.0
        guard = solver.plugin_manager.dispatch("on_inner_guard", solver, dict(eval_ctx))
        if isinstance(guard, Mapping) and not bool(guard.get("allow", True)):
            self.stats["blocked"] += 1.0
            obj, vio = self._fallback(solver)
            return obj, float(vio)

        start = time.perf_counter()
        attempts = max(1, int(self.cfg.max_retries) + 1)
        inner_result: Optional[Dict[str, Any]] = None
        last_exc: Optional[Exception] = None
        for attempt in range(attempts):
            try:
                inner_result = self._run_task_with_timeout(task, eval_ctx)
                break
            except Exception as exc:
                last_exc = exc
                if attempt + 1 < attempts:
                    self.stats["retries"] += 1.0
                    backoff_ms = float(self.cfg.retry_backoff_ms)
                    if backoff_ms > 0:
                        time.sleep(backoff_ms / 1000.0)
                continue
        if inner_result is None:
            self.stats["failure"] += 1.0
            if self.cfg.warn_on_failure:
                print(f"[inner-solver:{self.name}] failed: {last_exc}")
            self.stats["fallback"] += 1.0
            obj, vio = self._fallback(solver)
            return obj, float(vio)
        elapsed_ms = float((time.perf_counter() - start) * 1000.0)
        self.stats["last_elapsed_ms"] = elapsed_ms

        status = str(inner_result.get("status", "ok"))
        success = status.lower() in {"ok", "success", "completed"}
        if success:
            self.stats["success"] += 1.0
        else:
            self.stats["failure"] += 1.0

        packet = {
            "source_layer": self.cfg.source_layer,
            "target_layer": self.cfg.target_layer,
            "candidate_id": eval_ctx["individual_id"],
            "generation": eval_ctx["generation"],
            "result": dict(inner_result),
            "elapsed_ms": elapsed_ms,
            "status": status,
        }
        solver.plugin_manager.dispatch("on_inner_result", solver, packet)

        mapper = getattr(problem, "evaluate_from_inner_result", None)
        if callable(mapper):
            mapped = mapper(x_arr, inner_result, eval_ctx)
        else:
            mapped = inner_result.get("objectives", inner_result.get("objective", self.cfg.fallback_penalty))

        obj = normalize_objectives(mapped, num_objectives=int(getattr(solver, "num_objectives", 1)), name="inner_result.objectives")
        violation = normalize_violation(inner_result.get("violation", 0.0), name="inner_result.violation")

        context = build_minimal_context(
            generation=eval_ctx["generation"],
            individual_id=eval_ctx["individual_id"],
            constraints=[],
            constraint_violation=violation,
            extra={"problem": problem},
        )
        metrics = context.get(KEY_METRICS)
        if not isinstance(metrics, dict):
            metrics = {}
            context[KEY_METRICS] = metrics
        metrics[KEY_METRICS_INNER_ELAPSED_MS.split(".", 1)[1]] = elapsed_ms
        metrics[KEY_METRICS_INNER_STATUS.split(".", 1)[1]] = status
        metrics[KEY_METRICS_INNER_CALLS.split(".", 1)[1]] = float(self.stats["calls"])

        obj = self._apply_bias(solver, x_arr, obj, individual_id, context)
        if bool(getattr(solver, "ignore_constraint_violation_when_bias", False)) and bool(
            getattr(solver, "enable_bias", False)
        ):
            violation = 0.0
        return obj, float(violation)

    def get_report(self) -> Optional[Dict[str, Any]]:
        out = super().get_report() or {}
        out["stats"] = dict(self.stats)
        out["source_layer"] = self.cfg.source_layer
        out["target_layer"] = self.cfg.target_layer
        return out
