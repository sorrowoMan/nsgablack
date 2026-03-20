from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple

import numpy as np

from ..base import Plugin
from ...utils.constraints.constraint_utils import evaluate_constraints_safe
from ...utils.extension_contracts import ContractError, normalize_candidate
from ...utils.context.context_keys import (
    KEY_METRICS,
    KEY_METRICS_MC_MAX,
    KEY_METRICS_MC_MEAN,
    KEY_METRICS_MC_MIN,
    KEY_METRICS_MC_SAMPLES,
    KEY_METRICS_MC_STD,
)


@dataclass
class MonteCarloEvaluationConfig:
    mc_samples: int = 16
    reduce: str = "mean"  # "mean" or "cvar"
    cvar_alpha: float = 0.2  # used when reduce="cvar" (lower tail for minimization)
    random_seed: Optional[int] = 0


class MonteCarloEvaluationProviderPlugin(Plugin):
    is_algorithmic = False
    context_requires = ()
    context_provides = (
        KEY_METRICS_MC_SAMPLES,
        KEY_METRICS_MC_MEAN,
        KEY_METRICS_MC_STD,
        KEY_METRICS_MC_MIN,
        KEY_METRICS_MC_MAX,
    )
    context_mutates = (KEY_METRICS,)
    context_cache = ()
    context_notes = (
        "Per-candidate Monte Carlo evaluation; writes MC statistics into context.metrics "
        "and returns reduced objective values."
    )
    """Monte Carlo L4 provider factory.

    Add as a plugin (auto-registers the provider on attach), or call
    `solver.register_evaluation_provider(...create_provider())` manually.
    """

    # Soft partner contracts (informational; no hard dependency).
    provides_metrics = {"mc_mean", "mc_std", "mc_samples", "mc_min", "mc_max"}

    def __init__(
        self,
        name: str = "monte_carlo_evaluation",
        *,
        config: Optional[MonteCarloEvaluationConfig] = None,
        priority: int = 10,
    ) -> None:
        super().__init__(name=str(name), priority=int(priority))
        self.cfg = config or MonteCarloEvaluationConfig()
        self._rng = np.random.default_rng(self.cfg.random_seed)
        self._provider = None

    def attach(self, solver) -> None:
        super().attach(solver)
        if self._provider is not None:
            return
        provider = self.create_provider()
        self._provider = provider
        register = getattr(solver, "register_evaluation_provider", None)
        if callable(register):
            register(provider)

    def detach(self, solver) -> None:
        provider = self._provider
        self._provider = None
        unregister = getattr(solver, "unregister_evaluation_provider", None)
        if callable(unregister) and provider is not None:
            try:
                unregister(provider)
            except Exception:
                pass
        super().detach(solver)

    def __getattr__(self, item: str):
        if str(item) == "evaluate_population":
            def _compat(solver, population: np.ndarray, context: Optional[Dict[str, Any]] = None):
                _ = context
                return self.evaluate_population_runtime(solver, population)

            return _compat
        raise AttributeError(item)

    def evaluate_population_runtime(self, solver, population: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        pop = np.asarray(population)
        if pop.ndim == 1:
            pop = pop.reshape(1, -1)
        if pop.ndim != 2:
            raise ContractError("MC plugin expects population as 2D array")

        n = int(pop.shape[0])
        m = int(getattr(solver, "num_objectives", 1) or 1)
        samples = max(1, int(self.cfg.mc_samples))

        objectives = np.zeros((n, m), dtype=float)
        violations = np.zeros((n,), dtype=float)

        for i in range(n):
            x = normalize_candidate(pop[i], dimension=int(solver.dimension), name=f"population[{i}]")

            # constraints once
            cons, vio = evaluate_constraints_safe(solver.problem, x)
            violations[i] = float(vio)

            # MC objective samples
            ys = []
            for _ in range(samples):
                # Compatibility boundary:
                # If problem.evaluate() uses global numpy RNG, isolate it per sample
                # so the outer solver RNG stream is not polluted.
                seed = int(self._rng.integers(0, 2**31 - 1))
                prev_state = None
                try:
                    prev_state = np.random.get_state()
                    np.random.seed(seed)
                    val = solver.problem.evaluate(x)
                finally:
                    if prev_state is not None:
                        try:
                            np.random.set_state(prev_state)
                        except Exception:
                            pass
                y = np.asarray(val, dtype=float).ravel()
                if y.size == 1 and m > 1:
                    # pad for compatibility
                    padded = np.zeros((m,), dtype=float)
                    padded[0] = float(y[0])
                    y = padded
                if y.size != m:
                    y = y[:m] if y.size > m else np.pad(y, (0, m - y.size))
                ys.append(y)
            Y = np.stack(ys, axis=0)  # (S, M)

            reduced = self._reduce(Y)
            # Expose MC statistics to downstream capability layers (e.g. Bias).
            # Keep the solver base pure: stats are carried via context["metrics"].
            ctx = solver.build_context(individual_id=i, constraints=cons, violation=float(violations[i]))
            ctx_metrics = ctx.get(KEY_METRICS)
            if not isinstance(ctx_metrics, dict):
                ctx_metrics = {}
                ctx[KEY_METRICS] = ctx_metrics
            ctx_metrics.update(self._stats(Y))
            if getattr(solver, "enable_bias", False) and getattr(solver, "bias_module", None) is not None:
                reduced = solver._apply_bias(np.asarray(reduced, dtype=float), x, i, ctx)
            objectives[i] = np.asarray(reduced, dtype=float)

        return objectives, violations

    def _stats(self, Y: np.ndarray) -> Dict[str, Any]:
        Y = np.asarray(Y, dtype=float)
        mean = np.mean(Y, axis=0)
        std = np.std(Y, axis=0, ddof=0)
        out: Dict[str, Any] = {
            "mc_samples": int(Y.shape[0]),
            "mc_mean": mean,
            "mc_std": std,
        }
        try:
            out["mc_min"] = np.min(Y, axis=0)
            out["mc_max"] = np.max(Y, axis=0)
        except Exception:
            pass
        return out

    def _reduce(self, Y: np.ndarray) -> np.ndarray:
        mode = str(self.cfg.reduce).lower().strip()
        if mode == "mean":
            return np.mean(Y, axis=0)
        if mode == "cvar":
            alpha = float(self.cfg.cvar_alpha)
            alpha = min(max(alpha, 0.0), 1.0)
            # minimization: CVaR on lower tail (best alpha fraction)
            k = max(1, int(np.ceil(alpha * Y.shape[0])))
            out = []
            for j in range(Y.shape[1]):
                col = np.sort(Y[:, j])
                out.append(float(np.mean(col[:k])))
            return np.asarray(out, dtype=float)
        return np.mean(Y, axis=0)

    def create_provider(self):
        owner = self

        class _Provider:
            name = owner.name
            semantic_mode = "equivalent"
            priority = int(getattr(owner, "priority", 0) or 0)

            def can_handle_individual(self, solver, x, context):
                _ = solver
                _ = context
                return x is not None

            def evaluate_individual(self, solver, x, context, individual_id=None):
                _ = context
                pop = np.asarray(x, dtype=float).reshape(1, -1)
                objs, vios = owner.evaluate_population_runtime(solver, pop)
                return np.asarray(objs[0], dtype=float).reshape(-1), float(vios[0])

            def can_handle_population(self, solver, population, context):
                _ = solver
                _ = context
                return population is not None

            def evaluate_population(self, solver, population, context):
                _ = context
                return owner.evaluate_population_runtime(solver, np.asarray(population, dtype=float))

        return _Provider()


