from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple

import numpy as np

from ...utils.constraints.constraint_utils import evaluate_constraints_safe
from ...utils.context.context_keys import KEY_METRICS
from .provider_plugin_base import EvaluationProviderPluginBase


@dataclass
class GpuEvaluationTemplateConfig:
    """Minimal config for GPU evaluation template plugin."""

    preferred_backend: str = "auto"  # auto | torch | cupy
    device: str = "cuda:0"
    fallback_to_solver_eval: bool = True
    warn_on_fallback: bool = True


class GpuEvaluationTemplateProviderPlugin(EvaluationProviderPluginBase):
    """GPU L4 provider factory (semantic equivalent)."""

    context_requires = ("problem",)
    context_provides = ("metrics.gpu_backend", "metrics.gpu_calls", "metrics.gpu_fallbacks")
    context_mutates = (KEY_METRICS,)
    context_cache = ()
    context_notes = (
        "Short-circuits evaluate_population only when backend + problem GPU path are available; "
        "otherwise returns None and keeps solver default path.",
    )

    def __init__(
        self,
        name: str = "gpu_eval_template",
        *,
        config: Optional[GpuEvaluationTemplateConfig] = None,
        priority: int = 80,
    ) -> None:
        super().__init__(name=str(name), priority=int(priority))
        self.name = str(name)
        self.priority = int(priority)
        self.cfg = config or GpuEvaluationTemplateConfig()
        self.stats: Dict[str, float] = {"calls": 0.0, "fallbacks": 0.0}

    def _select_backend(self) -> Optional[str]:
        pref = str(self.cfg.preferred_backend).lower()
        if pref in {"torch", "cupy"}:
            candidates = [pref]
        else:
            candidates = ["torch", "cupy"]
        for name in candidates:
            try:
                if name == "torch":
                    import torch  # type: ignore

                    if bool(torch.cuda.is_available()):
                        return "torch"
                if name == "cupy":
                    import cupy  # type: ignore  # noqa: F401

                    return "cupy"
            except Exception:
                continue
        return None

    def _evaluate_gpu_batch(self, problem: Any, population: np.ndarray, backend: str) -> Optional[np.ndarray]:
        hook = getattr(problem, "evaluate_gpu_batch", None)
        if callable(hook):
            out = hook(population, backend=backend, device=self.cfg.device)
            return np.asarray(out, dtype=float)
        return None

    def _evaluate_constraints(self, problem: Any, population: np.ndarray) -> np.ndarray:
        batch_hook = getattr(problem, "evaluate_constraints_batch", None)
        if callable(batch_hook):
            cons = np.asarray(batch_hook(population), dtype=float)
            if cons.ndim == 1:
                cons = cons.reshape(-1, 1)
            vio = np.sum(np.maximum(cons, 0.0), axis=1)
            return np.asarray(vio, dtype=float).reshape(-1)
        out = []
        for x in population:
            _, vio = evaluate_constraints_safe(problem, x)
            out.append(float(vio))
        return np.asarray(out, dtype=float).reshape(-1)

    def evaluate_population_runtime(self, solver, population: np.ndarray) -> Optional[Tuple[np.ndarray, np.ndarray]]:
        problem = getattr(solver, "problem", None)
        if problem is None:
            return None

        pop = np.asarray(population, dtype=float)
        if pop.ndim == 1:
            pop = pop.reshape(1, -1)
        if pop.size == 0:
            return None

        backend = self._select_backend()
        if backend is None:
            return None

        self.stats["calls"] += 1.0
        try:
            obj = self._evaluate_gpu_batch(problem, pop, backend=backend)
            if obj is None:
                return None
            if obj.ndim == 1:
                obj = obj.reshape(-1, 1)
            if int(obj.shape[0]) != int(pop.shape[0]):
                raise ValueError("gpu objective batch size mismatch")
            violations = self._evaluate_constraints(problem, pop)
        except Exception as exc:
            self.stats["fallbacks"] += 1.0
            if self.cfg.warn_on_fallback:
                print(f"[gpu-eval-template] fallback to solver path: {exc}")
            if self.cfg.fallback_to_solver_eval:
                return None
            raise

        # lightweight metrics sync
        getter = getattr(solver, "get_context", None)
        setter = getattr(solver, "set_context", None)
        if callable(getter) and callable(setter):
            try:
                ctx = getter() or {}
                metrics = ctx.get(KEY_METRICS)
                if not isinstance(metrics, dict):
                    metrics = {}
                    ctx[KEY_METRICS] = metrics
                metrics["gpu_backend"] = backend
                metrics["gpu_calls"] = float(self.stats["calls"])
                metrics["gpu_fallbacks"] = float(self.stats["fallbacks"])
                setter(ctx)
            except Exception:
                pass

        return np.asarray(obj, dtype=float), np.asarray(violations, dtype=float)

    def create_provider(self):
        owner = self

        class _Provider:
            name = owner.name
            semantic_mode = "equivalent"
            priority = int(getattr(owner, "priority", 0) or 0)

            def can_handle_individual(self, solver, x, context):
                _ = context
                return owner._select_backend() is not None and x is not None

            def evaluate_individual(self, solver, x, context, individual_id=None):
                _ = context
                pop = np.asarray(x, dtype=float).reshape(1, -1)
                out = owner.evaluate_population_runtime(solver, pop)
                if out is None:
                    return None
                objs, vios = out
                return np.asarray(objs[0], dtype=float).reshape(-1), float(vios[0])

            def can_handle_population(self, solver, population, context):
                _ = solver
                _ = context
                return owner._select_backend() is not None and population is not None

            def evaluate_population(self, solver, population, context):
                _ = context
                return owner.evaluate_population_runtime(solver, np.asarray(population, dtype=float))

        return _Provider()
