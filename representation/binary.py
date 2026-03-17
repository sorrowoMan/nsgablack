"""
Binary representation helpers.

"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Any

import numpy as np

from .base import RepresentationComponentContract
from ..core.state.context_keys import KEY_CAPACITY


@dataclass
class BinaryInitializer(RepresentationComponentContract):
    probability: float = 0.5
    context_requires = ()
    context_provides = ()
    context_mutates = ()
    context_cache = ()
    context_notes = ("Initializer is pure random Bernoulli sampling; no context I/O.",)

    def __post_init__(self) -> None:
        self._rng = np.random.default_rng()

    def initialize(self, problem: Any, context: Optional[dict] = None) -> np.ndarray:
        return (self._rng.random(problem.dimension) < self.probability).astype(int)


@dataclass
class BitFlipMutation(RepresentationComponentContract):
    rate: float = 0.01
    context_requires = ()
    context_provides = ()
    context_mutates = ()
    context_cache = ()
    context_notes = ("Bit-flip mutation is stateless; no context I/O.",)

    def __post_init__(self) -> None:
        self._rng = np.random.default_rng()

    def mutate(self, x: np.ndarray, context: Optional[dict] = None) -> np.ndarray:
        mutated = np.array(x, copy=True)
        mask = self._rng.random(len(mutated)) < self.rate
        mutated[mask] = 1 - mutated[mask]
        return mutated


@dataclass
class BinaryRepair(RepresentationComponentContract):
    threshold: float = 0.5
    context_requires = ()
    context_provides = ()
    context_mutates = ()
    context_cache = ()
    context_notes = ("Threshold projection only; no context I/O.",)

    def repair(self, x: np.ndarray, context: Optional[dict] = None) -> np.ndarray:
        return (x >= self.threshold).astype(int)


@dataclass
class BinaryCapacityRepair(RepresentationComponentContract):
    capacity: int
    exact: bool = False
    context_requires = (KEY_CAPACITY,)
    context_provides = ()
    context_mutates = ()
    context_cache = ()
    context_notes = ("Reads knapsack-style capacity from context (or falls back to constructor value).",)

    def __post_init__(self) -> None:
        self._rng = np.random.default_rng()

    def repair(self, x: np.ndarray, context: Optional[dict] = None) -> np.ndarray:
        vec = (np.array(x, copy=True) > 0.5).astype(int)
        cap = self.capacity
        if context and KEY_CAPACITY in context:
            cap = int(context[KEY_CAPACITY])

        ones = np.where(vec == 1)[0].tolist()
        zeros = np.where(vec == 0)[0].tolist()
        if len(ones) > cap:
            drop = self._rng.choice(ones, size=len(ones) - cap, replace=False)
            vec[drop] = 0
        elif self.exact and len(ones) < cap and zeros:
            add = self._rng.choice(zeros, size=min(cap - len(ones), len(zeros)), replace=False)
            vec[add] = 1
        return vec
