"""
Uncertainty-driven exploration bias.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional
import numpy as np

from ...core.base import AlgorithmicBias, OptimizationContext


@dataclass
class UncertaintyExplorationBias(AlgorithmicBias):
    """
    Encourage exploration when uncertainty is high.

    Consumes `surrogate_std` (or `surrogate_uncertainty`) from context.metrics.
    If missing, returns 0.0 safely.
    """

    name: str = "uncertainty_exploration"
    weight: float = 0.2
    metric_key: str = "surrogate_std"
    alt_key: str = "surrogate_uncertainty"
    power: float = 1.0

    requires_metrics = ("surrogate_std", "surrogate_uncertainty")
    recommended_plugins = ("plugin.surrogate_eval",)

    def compute(self, x: np.ndarray, context: OptimizationContext) -> float:
        metrics = getattr(context, "metrics", {}) or {}
        val = None
        if isinstance(metrics, dict):
            if self.metric_key in metrics:
                val = metrics.get(self.metric_key)
            elif self.alt_key in metrics:
                val = metrics.get(self.alt_key)
        if val is None:
            return 0.0
        try:
            arr = np.asarray(val, dtype=float).ravel()
            if arr.size == 0:
                return 0.0
            score = float(np.mean(arr))
        except Exception:
            try:
                score = float(val)
            except Exception:
                return 0.0
        score = max(0.0, score)
        if self.power != 1.0:
            score = float(score) ** float(self.power)
        # exploration: subtract from objective (reward), so return negative
        return -float(score)
