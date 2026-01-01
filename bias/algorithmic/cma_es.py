"""
CMA-ES style bias.

This bias uses a mean vector and covariance (if available) to encourage
solutions to follow an adaptive search distribution.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import numpy as np

from ..core.base import AlgorithmicBias, OptimizationContext


@dataclass
class CMAESBias(AlgorithmicBias):
    """
    CMA-ES-inspired bias based on distance to mean and covariance.

    Context usage (optional):
    - context.metrics['mean'] or context.problem_data['mean']
    - context.metrics['cov'] or context.problem_data['cov']
    - context.metrics['sigma'] or context.problem_data['sigma']
    """

    weight: float = 0.1
    scale: float = 0.1
    name: str = field(default="cma_es_bias", init=False)

    def __post_init__(self):
        super().__init__(self.name, self.weight, adaptive=True)

    def compute(self, x: np.ndarray, context: OptimizationContext) -> float:
        mean = self._get_array(context, "mean")
        if mean is None:
            return 0.0

        cov = self._get_array(context, "cov")
        sigma = self._get_scalar(context, "sigma", default=1.0)

        diff = x - mean
        if cov is None:
            dist = float(np.linalg.norm(diff))
        else:
            try:
                cov = np.asarray(cov, dtype=float)
                inv = np.linalg.pinv(cov)
                dist = float(np.sqrt(diff.T @ inv @ diff))
            except Exception:
                dist = float(np.linalg.norm(diff))

        return self.scale * (dist / (dist + 1.0)) * sigma

    @staticmethod
    def _get_array(context: OptimizationContext, key: str) -> Optional[np.ndarray]:
        if hasattr(context, "metrics") and key in context.metrics:
            return np.asarray(context.metrics[key], dtype=float)
        if hasattr(context, "problem_data") and key in context.problem_data:
            return np.asarray(context.problem_data[key], dtype=float)
        return None

    @staticmethod
    def _get_scalar(context: OptimizationContext, key: str, default: float) -> float:
        if hasattr(context, "metrics") and key in context.metrics:
            return float(context.metrics[key])
        if hasattr(context, "problem_data") and key in context.problem_data:
            return float(context.problem_data[key])
        return default


@dataclass
class AdaptiveCMAESBias(CMAESBias):
    """
    Adaptive CMA-ES bias that shrinks scale over generations.
    """

    min_scale: float = 0.02
    max_scale: float = 0.2
    name: str = field(default="adaptive_cma_es_bias", init=False)

    def compute(self, x: np.ndarray, context: OptimizationContext) -> float:
        max_g = context.metrics.get("max_generations", 100) if hasattr(context, "metrics") else 100
        ratio = min(1.0, max(0.0, context.generation / float(max_g)))
        self.scale = self.max_scale - (self.max_scale - self.min_scale) * ratio
        return super().compute(x, context)


__all__ = ["CMAESBias", "AdaptiveCMAESBias"]
