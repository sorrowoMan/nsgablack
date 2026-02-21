"""
Levy flight bias.

Encourages larger exploratory steps early and smaller steps later.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from ..core.base import AlgorithmicBias, OptimizationContext


@dataclass
class LevyFlightBias(AlgorithmicBias):
    """
    Levy flight-inspired bias based on distance from population center.
    """
    context_requires = ("generation", "population")
    requires_metrics = ("max_generations",)
    metrics_fallback = "default"
    context_provides = ()
    context_mutates = ()
    context_cache = ()
    context_notes = "Reads context fields: generation, metrics, population; outputs scalar bias only."



    weight: float = 0.1
    exploration_phase: float = 0.3
    scale: float = 0.2
    name: str = field(default="levy_flight_bias", init=False)

    def __post_init__(self):
        super().__init__(self.name, self.weight, adaptive=True)

    def compute(self, x: np.ndarray, context: OptimizationContext) -> float:
        if not context.population:
            return 0.0

        center = np.mean(np.asarray(context.population), axis=0)
        dist = float(np.linalg.norm(x - center))
        max_g = context.metrics.get("max_generations", 100) if hasattr(context, "metrics") else 100
        ratio = min(1.0, max(0.0, context.generation / float(max_g)))

        if ratio < self.exploration_phase:
            # Reward larger steps early
            return -self.scale * (dist / (dist + 1.0))
        # Penalize large steps later to encourage convergence
        return self.scale * (dist / (dist + 1.0))


__all__ = ["LevyFlightBias"]
