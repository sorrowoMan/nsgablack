"""
Continuous representation helpers.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Any

import numpy as np


@dataclass
class UniformInitializer:
    low: float = 0.0
    high: float = 1.0

    def initialize(self, problem: Any, context: Optional[dict] = None) -> np.ndarray:
        return np.random.uniform(self.low, self.high, problem.dimension)


@dataclass
class GaussianMutation:
    sigma: float = 0.1
    low: Optional[float] = None
    high: Optional[float] = None

    def mutate(self, x: np.ndarray, context: Optional[dict] = None) -> np.ndarray:
        mutated = x + np.random.normal(0.0, self.sigma, size=x.shape)
        if self.low is not None and self.high is not None:
            mutated = np.clip(mutated, self.low, self.high)
        return mutated


@dataclass
class ClipRepair:
    low: float = 0.0
    high: float = 1.0

    def repair(self, x: np.ndarray, context: Optional[dict] = None) -> np.ndarray:
        return np.clip(x, self.low, self.high)
