"""
Risk bias (CVaR / worst-case) driven by evaluation statistics.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional
import numpy as np

from ..core.base import DomainBias, OptimizationContext


@dataclass
class RiskBias(DomainBias):
    """
    Risk-aware bias using evaluation statistics.

    Supported modes:
    - "cvar": approximate CVaR using mean + k * std (k derived from alpha)
    - "worst_case": use worst observed metric (mc_max or mc_min)

    This bias consumes metrics from context.metrics (e.g., provided by
    MonteCarloEvaluationProviderPlugin).
    """
    context_requires = ("problem_data",)
    context_provides = ()
    context_mutates = ()
    context_cache = ()
    context_notes = "Reads context fields: problem_data; outputs scalar bias only."



    mode: str = "cvar"
    alpha: float = 0.2
    std_scale: float = 1.0
    metric_prefix: str = "mc"

    requires_metrics = ("mc_mean", "mc_std", "mc_min", "mc_max")
    metrics_fallback = "safe_zero"
    recommended_plugins = ("plugin.monte_carlo_eval",)

    def __init__(
        self,
        name: str = "risk_bias",
        *,
        weight: float = 0.2,
        mode: str = "cvar",
        alpha: float = 0.2,
        std_scale: float = 1.0,
        metric_prefix: str = "mc",
        mandatory: bool = False,
    ) -> None:
        super().__init__(name=name, weight=weight, mandatory=mandatory)
        self.mode = str(mode or "cvar").lower().strip()
        self.alpha = float(alpha)
        self.std_scale = float(std_scale)
        self.metric_prefix = str(metric_prefix or "mc")

    def compute(self, x: np.ndarray, context: OptimizationContext) -> float:
        metrics = getattr(context, "metrics", {}) or {}
        if not isinstance(metrics, dict):
            return 0.0

        mean = metrics.get(f"{self.metric_prefix}_mean")
        std = metrics.get(f"{self.metric_prefix}_std")
        mmin = metrics.get(f"{self.metric_prefix}_min")
        mmax = metrics.get(f"{self.metric_prefix}_max")

        if self.mode == "worst_case":
            val = self._coerce_vector(mmax if mmax is not None else mmin)
            return float(np.mean(val)) if val is not None else 0.0

        # cvar-like approximation using mean + k * std
        mean_v = self._coerce_vector(mean)
        std_v = self._coerce_vector(std)
        if mean_v is None or std_v is None:
            return 0.0
        k = self._alpha_to_k(self.alpha)
        approx = mean_v + (k * self.std_scale) * std_v
        return float(np.mean(approx))

    @staticmethod
    def _coerce_vector(val: Optional[object]) -> Optional[np.ndarray]:
        if val is None:
            return None
        try:
            arr = np.asarray(val, dtype=float).ravel()
            if arr.size == 0:
                return None
            return arr
        except Exception:
            try:
                return np.asarray([float(val)], dtype=float)
            except Exception:
                return None

    @staticmethod
    def _alpha_to_k(alpha: float) -> float:
        # Heuristic: larger alpha -> smaller tail penalty
        a = min(max(float(alpha), 1e-6), 1.0)
        return float(np.sqrt(1.0 / max(a, 1e-6)))
