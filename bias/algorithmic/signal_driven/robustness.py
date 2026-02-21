"""
Robustness bias.

This bias is designed to work with capability plugins that provide
stochastic evaluation statistics (e.g. MonteCarloEvaluationPlugin).

Expected context:
- context.metrics["mc_std"]: per-objective standard deviation (array-like)
- context.metrics["mc_mean"]: per-objective mean (array-like, optional)

When the metrics are missing, the bias safely degrades to 0.0 (no-op).
"""

from __future__ import annotations

from typing import Any
import warnings

import numpy as np

from ...core.base import AlgorithmicBias, OptimizationContext


class RobustnessBias(AlgorithmicBias):
    """Penalize candidates with high stochastic uncertainty."""
    context_requires = ()
    context_provides = ()
    context_mutates = ()
    context_cache = ()
    context_notes = "Reads context fields: metrics; outputs scalar bias only."



    # Soft partner contracts (informational; no hard dependency).
    requires_metrics = ("mc_std",)
    metrics_fallback = "safe_zero"
    recommended_plugins = ["MonteCarloEvaluationPlugin"]

    def __init__(
        self,
        weight: float = 0.1,
        *,
        aggregate: str = "mean",  # "mean" | "sum" | "l2"
        power: float = 1.0,
        name: str = "robustness",
    ) -> None:
        super().__init__(name, weight, adaptive=True)
        self.aggregate = str(aggregate).lower().strip()
        self.power = float(power)
        self._missing_metrics_warned = False

    def compute(self, x: np.ndarray, context: OptimizationContext) -> float:
        std = context.metrics.get("mc_std")
        if std is None:
            if not self._missing_metrics_warned:
                warnings.warn(
                    "RobustnessBias 未检测到 context.metrics['mc_std']，将退化为 0.0。"
                    "如需鲁棒性/稳定性引导，请配合提供 MC 统计的能力层插件（例如 MonteCarloEvaluationPlugin）。",
                    RuntimeWarning,
                    stacklevel=2,
                )
                self._missing_metrics_warned = True
            return 0.0

        std_arr = self._to_1d_float(std)
        if std_arr.size == 0:
            return 0.0

        val = self._aggregate(std_arr)
        if self.power != 1.0:
            val = float(val) ** float(self.power)
        return float(self.weight) * float(val)

    def _aggregate(self, v: np.ndarray) -> float:
        if self.aggregate == "sum":
            return float(np.sum(v))
        if self.aggregate == "l2":
            return float(np.sqrt(np.sum(v * v)))
        return float(np.mean(v))

    @staticmethod
    def _to_1d_float(value: Any) -> np.ndarray:
        try:
            arr = np.asarray(value, dtype=float).reshape(-1)
        except Exception:
            return np.asarray([], dtype=float)
        return arr

