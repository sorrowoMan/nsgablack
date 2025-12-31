"""
Binary representation helpers.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Any

import numpy as np


@dataclass
class BinaryInitializer:
    probability: float = 0.5

    def initialize(self, problem: Any, context: Optional[dict] = None) -> np.ndarray:
        return (np.random.rand(problem.dimension) < self.probability).astype(int)


@dataclass
class BitFlipMutation:
    rate: float = 0.01

    def mutate(self, x: np.ndarray, context: Optional[dict] = None) -> np.ndarray:
        mutated = np.array(x, copy=True)
        mask = np.random.rand(len(mutated)) < self.rate
        mutated[mask] = 1 - mutated[mask]
        return mutated


@dataclass
class BinaryRepair:
    threshold: float = 0.5

    def repair(self, x: np.ndarray, context: Optional[dict] = None) -> np.ndarray:
        return (x >= self.threshold).astype(int)


@dataclass
class BinaryCapacityRepair:
    capacity: int
    exact: bool = False

    def repair(self, x: np.ndarray, context: Optional[dict] = None) -> np.ndarray:
        vec = (np.array(x, copy=True) > 0.5).astype(int)
        cap = self.capacity
        if context and "capacity" in context:
            cap = int(context["capacity"])

        ones = np.where(vec == 1)[0].tolist()
        zeros = np.where(vec == 0)[0].tolist()
        if len(ones) > cap:
            drop = np.random.choice(ones, size=len(ones) - cap, replace=False)
            vec[drop] = 0
        elif self.exact and len(ones) < cap and zeros:
            add = np.random.choice(zeros, size=min(cap - len(ones), len(zeros)), replace=False)
            vec[add] = 1
        return vec
