from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, Mapping, Optional, Tuple

import numpy as np

from ...utils.context.context_keys import KEY_METRICS
from ...core.state.context_schema import build_minimal_context
from ...utils.extension_contracts import normalize_objectives, normalize_violation
from ..solver_backends.backend_contract import BackendSolveRequest, normalize_backend_output


BackendFactory = Callable[[Any, Dict[str, Any]], Any]


@dataclass
class EvaluationModelConfig:
    scope: str = "both"  # outer | inner | both
    fallback_penalty: float = 1e6
    warn_on_failure: bool = True
    update_context_metrics: bool = True


class EvaluationModelProviderPlugin:
    """Evaluation-model L4 provider factory."""

    context_requires = ("problem",)
    context_provides = ("metrics.eval_model_calls", "metrics.eval_model_failures")
    context_mutates = (KEY_METRICS,)
    context_cache = ()
    context_notes = (
        "Provides unified backend-based evaluation for both outer evaluate_individual and inner delegation.",
    )

    def __init__(
        self,
        name: str = "evaluation_model",
        *,
        config: Optional[EvaluationModelConfig] = None,
        backend_factory: Optional[BackendFactory] = None,
        priority: int = 75,
    ) -> None:
        self.name = str(name)
        self.priority = int(priority)
        self.cfg = config or EvaluationModelConfig()
        self.backend_factory = backend_factory
        self.stats: Dict[str, float] = {"calls": 0.0, "failures": 0.0}
        self.allow_inner = True

    def _scope_enabled(self, mode: str) -> bool:
        scope = str(self.cfg.scope or "both").strip().lower()
        if scope == "both":
            return True
        return scope == mode

    def _build_backend(self, solver: Any, eval_ctx: Dict[str, Any]) -> Any:
        problem = getattr(solver, "problem", None)
        if callable(self.backend_factory):
            return self.backend_factory(problem, eval_ctx)
        hook = getattr(problem, "build_evaluation_backend", None) if problem is not None else None
        if callable(hook):
            return hook(eval_ctx)
        return None

    def evaluate_model(self, solver: Any, request: BackendSolveRequest) -> Mapping[str, Any]:
        eval_ctx = dict(request.eval_context or {})
        mode = str(eval_ctx.get("scope", "inner")).strip().lower()
        if not self._scope_enabled("inner" if mode != "outer" else "outer"):
            raise RuntimeError(f"evaluation-model scope={self.cfg.scope} does not allow mode={mode}")
        backend = self._build_backend(solver, eval_ctx)
        if backend is None or not callable(getattr(backend, "solve", None)):
            raise RuntimeError("evaluation backend is not configured or not callable")
        raw = backend.solve(request)
        if not isinstance(raw, Mapping):
            raise TypeError("evaluation backend solve() must return mapping")
        return normalize_backend_output(raw)

    def _update_metrics(self, solver: Any) -> None:
        if not bool(self.cfg.update_context_metrics):
            return
        getter = getattr(solver, "get_context", None)
        setter = getattr(solver, "set_context", None)
        if not callable(getter) or not callable(setter):
            return
        try:
            ctx = getter() or {}
            metrics = ctx.get(KEY_METRICS)
            if not isinstance(metrics, dict):
                metrics = {}
                ctx[KEY_METRICS] = metrics
            metrics["eval_model_calls"] = float(self.stats["calls"])
            metrics["eval_model_failures"] = float(self.stats["failures"])
            setter(ctx)
        except Exception:
            return

    def evaluate_individual_runtime(self, solver, x: np.ndarray, individual_id: Optional[int] = None):
        if not self._scope_enabled("outer"):
            return None
        candidate = np.asarray(x, dtype=float).reshape(-1)
        eval_ctx: Dict[str, Any] = {
            "generation": int(getattr(solver, "generation", 0)),
            "individual_id": 0 if individual_id is None else int(individual_id),
            "layer": "L1",
            "scope": "outer",
        }
        request = BackendSolveRequest(
            candidate=candidate,
            eval_context=eval_ctx,
            inner_problem=None,
            inner_solver=None,
            payload={},
        )
        self.stats["calls"] += 1.0
        try:
            out = dict(self.evaluate_model(solver, request))
        except Exception as exc:
            self.stats["failures"] += 1.0
            if self.cfg.warn_on_failure:
                print(f"[evaluation-model:{self.name}] outer eval failed: {exc}")
            penalty = float(self.cfg.fallback_penalty)
            n_obj = int(getattr(solver, "num_objectives", 1))
            obj = np.full((n_obj,), penalty, dtype=float)
            vio = penalty
            self._update_metrics(solver)
            return obj, float(vio)

        obj = normalize_objectives(
            out.get("objectives", out.get("objective", self.cfg.fallback_penalty)),
            num_objectives=int(getattr(solver, "num_objectives", 1)),
            name="evaluation_model.objectives",
        )
        vio = normalize_violation(out.get("violation", 0.0), name="evaluation_model.violation")

        # Keep parity with inner plugin style context build.
        _ = build_minimal_context(
            generation=eval_ctx["generation"],
            individual_id=eval_ctx["individual_id"],
            constraints=[],
            constraint_violation=vio,
            extra={"problem": getattr(solver, "problem", None)},
        )
        self._update_metrics(solver)
        return obj, float(vio)

    def create_provider(self):
        owner = self

        class _Provider:
            name = owner.name
            semantic_mode = "equivalent"
            allow_inner = owner.allow_inner

            def can_handle_individual(self, solver, x, context):
                _ = solver
                _ = x
                _ = context
                return owner._scope_enabled("outer")

            def evaluate_individual(self, solver, x, context, individual_id=None):
                _ = context
                return owner.evaluate_individual_runtime(
                    solver,
                    np.asarray(x, dtype=float),
                    individual_id=individual_id,
                )

            def can_handle_population(self, solver, population, context):
                _ = solver
                _ = population
                _ = context
                return False

            def evaluate_population(self, solver, population, context):
                _ = solver
                _ = population
                _ = context
                return None

            def evaluate_model(self, solver, request):
                return owner.evaluate_model(solver, request)

        return _Provider()
