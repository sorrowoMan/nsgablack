"""
Tabu Search bias.

This bias penalizes solutions that are too close to recently visited ones.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List

import numpy as np

from ..core.base import AlgorithmicBias, OptimizationContext


@dataclass
class TabuSearchBias(AlgorithmicBias):
    """
    Tabu search-inspired bias.

    Maintains a short-term tabu list of recent solutions and penalizes
    candidates that are too close to them.
    """
    context_requires = ()
    requires_metrics = ()
    context_provides = ()
    context_mutates = ()
    context_cache = ()
    context_notes = "Reads context fields: metrics; outputs scalar bias only."



    weight: float = 0.15
    tabu_size: int = 30
    distance_threshold: float = 0.1
    penalty_scale: float = 0.5
    name: str = field(default="tabu_search_bias", init=False)

    def __post_init__(self):
        super().__init__(self.name, self.weight, adaptive=False)
        self._tabu_list: List[np.ndarray] = []

    def compute(self, x: np.ndarray, context: OptimizationContext) -> float:
        if not self._tabu_list:
            self._remember(x)
            return 0.0

        distances = [np.linalg.norm(x - t) for t in self._tabu_list]
        min_dist = float(np.min(distances)) if distances else float("inf")

        self._remember(x)

        if min_dist >= self.distance_threshold:
            return 0.0
        # Penalize being too close to tabu points
        return self.penalty_scale * (1.0 - min_dist / max(self.distance_threshold, 1e-9))

    def _remember(self, x: np.ndarray):
        self._tabu_list.append(np.array(x, copy=True))
        if len(self._tabu_list) > self.tabu_size:
            self._tabu_list.pop(0)


__all__ = ["TabuSearchBias"]
