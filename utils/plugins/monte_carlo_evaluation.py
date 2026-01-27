from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple

import numpy as np

from .base import Plugin
from ..constraints.constraint_utils import evaluate_constraints_safe
from ..extension_contracts import ContractError, normalize_candidate


@dataclass
class MonteCarloEvaluationConfig:
    mc_samples: int = 16
    reduce: str = "mean"  # "mean" or "cvar"
    cvar_alpha: float = 0.2  # used when reduce="cvar" (lower tail for minimization)
    random_seed: Optional[int] = 0


class MonteCarloEvaluationPlugin(Plugin):
    is_algorithmic = True
    """Monte Carlo evaluation as a capability plugin.

    It overrides `evaluate_population` (short-circuit hook) and aggregates multiple
    stochastic evaluations per candidate.

    Notes:
    - This plugin assumes the stochasticity lives inside `problem.evaluate(x)`.
    - Constraints are evaluated once per candidate (common case: deterministic constraints).
    - Bias application is delegated back to the solver via `solver._apply_bias(...)`.
    """

    # Soft partner contracts (informational; no hard dependency).
    provides_metrics = {"mc_mean", "mc_std", "mc_samples", "mc_min", "mc_max"}

    def __init__(
        self,
        name: str = "monte_carlo_evaluation",
        *,
        config: Optional[MonteCarloEvaluationConfig] = None,
    ) -> None:
        super().__init__(name=name)
        self.cfg = config or MonteCarloEvaluationConfig()
        self._rng = np.random.default_rng(self.cfg.random_seed)

    def evaluate_population(self, solver, population: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
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
                # allow per-sample randomness control if user uses numpy global RNG
                try:
                    np.random.seed(int(self._rng.integers(0, 2**31 - 1)))
                except Exception:
                    pass
                val = solver.problem.evaluate(x)
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
            ctx_metrics = ctx.get("metrics")
            if not isinstance(ctx_metrics, dict):
                ctx_metrics = {}
                ctx["metrics"] = ctx_metrics
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
