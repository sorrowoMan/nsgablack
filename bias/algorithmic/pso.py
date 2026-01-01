"""
Particle Swarm Optimization (PSO) style bias.

This bias encourages movement toward global/local best positions when available
in the optimization context.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import numpy as np

from ..core.base import AlgorithmicBias, OptimizationContext


@dataclass
class ParticleSwarmBias(AlgorithmicBias):
    """
    PSO-inspired bias that attracts solutions toward best-known positions.

    Context usage (optional):
    - context.metrics['global_best_x'] or context.problem_data['global_best_x']
    - context.metrics['local_best_x'] or context.problem_data['local_best_x']
    """

    weight: float = 0.1
    social_weight: float = 1.5
    cognitive_weight: float = 1.0
    scale: float = 0.1
    name: str = field(default="pso_bias", init=False)

    def __post_init__(self):
        super().__init__(self.name, self.weight, adaptive=True)

    def compute(self, x: np.ndarray, context: OptimizationContext) -> float:
        global_best = self._get_best(context, "global_best_x")
        local_best = self._get_best(context, "local_best_x")

        if global_best is None and local_best is None:
            return 0.0

        bias_value = 0.0
        if global_best is not None:
            dist = float(np.linalg.norm(x - global_best))
            bias_value += self.social_weight * (dist / (dist + 1.0)) * self.scale
        if local_best is not None:
            dist = float(np.linalg.norm(x - local_best))
            bias_value += self.cognitive_weight * (dist / (dist + 1.0)) * self.scale

        return bias_value

    @staticmethod
    def _get_best(context: OptimizationContext, key: str) -> Optional[np.ndarray]:
        if hasattr(context, "metrics") and key in context.metrics:
            return np.asarray(context.metrics[key], dtype=float)
        if hasattr(context, "problem_data") and key in context.problem_data:
            return np.asarray(context.problem_data[key], dtype=float)
        return None


@dataclass
class AdaptivePSOBias(ParticleSwarmBias):
    """
    Adaptive PSO bias that shifts weights over generations.
    """

    min_social: float = 0.5
    max_social: float = 2.0
    min_cognitive: float = 0.5
    max_cognitive: float = 2.0
    name: str = field(default="adaptive_pso_bias", init=False)

    def compute(self, x: np.ndarray, context: OptimizationContext) -> float:
        max_g = context.metrics.get("max_generations", 100) if hasattr(context, "metrics") else 100
        ratio = min(1.0, max(0.0, context.generation / float(max_g)))
        self.social_weight = self.min_social + (self.max_social - self.min_social) * ratio
        self.cognitive_weight = self.max_cognitive - (self.max_cognitive - self.min_cognitive) * ratio
        return super().compute(x, context)


__all__ = ["ParticleSwarmBias", "AdaptivePSOBias"]
