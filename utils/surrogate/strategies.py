from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass
class UncertaintySampling:
    """Select indices with highest uncertainty."""

    def select(self, uncertainties: np.ndarray, n_samples: int = 1) -> list[int]:
        u = np.asarray(uncertainties, dtype=float).ravel()
        n = int(max(0, n_samples))
        if n == 0:
            return []
        n = min(n, u.size)
        idx = np.argsort(u)[-n:]
        return [int(i) for i in idx]


@dataclass
class AdaptiveStrategy:
    """A tiny exploration/exploitation schedule helper."""

    exploration_rate: float = 0.3
    current_exploration_rate: float = 0.3

    def __post_init__(self) -> None:
        self.current_exploration_rate = float(self.exploration_rate)

    def update_strategy(self, generation: int, max_generations: int) -> None:
        max_g = max(1, int(max_generations))
        g = max(0, int(generation))
        progress = min(1.0, g / max_g)
        self.current_exploration_rate = max(0.1, float(self.exploration_rate) * (1.0 - progress))

