"""
Integer representation helpers.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Any, Tuple

import numpy as np


def _get_bounds(problem: Any, context: Optional[dict]) -> Tuple[np.ndarray, np.ndarray]:
    bounds = None
    if context and "bounds" in context:
        bounds = context["bounds"]
    elif hasattr(problem, "bounds"):
        bounds = problem.bounds

    if bounds is None:
        raise ValueError("bounds are required for integer representation")

    if isinstance(bounds, dict):
        if hasattr(problem, "variables"):
            keys = list(problem.variables)
        else:
            keys = list(bounds.keys())
        lows = np.array([bounds[k][0] for k in keys], dtype=float)
        highs = np.array([bounds[k][1] for k in keys], dtype=float)
    else:
        arr = np.asarray(bounds, dtype=float)
        lows = arr[:, 0]
        highs = arr[:, 1]

    return lows, highs


@dataclass
class IntegerInitializer:
    low: Optional[int] = None
    high: Optional[int] = None

    def initialize(self, problem: Any, context: Optional[dict] = None) -> np.ndarray:
        if self.low is not None and self.high is not None:
            low = np.full(problem.dimension, self.low, dtype=int)
            high = np.full(problem.dimension, self.high, dtype=int)
        else:
            low_f, high_f = _get_bounds(problem, context)
            low = np.floor(low_f).astype(int)
            high = np.ceil(high_f).astype(int)

        high = np.maximum(high, low)
        return np.random.randint(low, high + 1)


@dataclass
class IntegerRepair:
    low: Optional[int] = None
    high: Optional[int] = None

    def repair(self, x: np.ndarray, context: Optional[dict] = None) -> np.ndarray:
        if self.low is not None and self.high is not None:
            low = self.low
            high = self.high
        else:
            if context and "bounds" in context:
                low_f, high_f = _get_bounds(None, context)
            elif context and "problem" in context:
                low_f, high_f = _get_bounds(context["problem"], context)
            else:
                low_f = np.full(x.shape, -np.inf)
                high_f = np.full(x.shape, np.inf)
            low = np.floor(low_f)
            high = np.ceil(high_f)

        repaired = np.round(x).astype(int)
        return np.clip(repaired, low, high)


@dataclass
class IntegerMutation:
    sigma: float = 0.5
    low: Optional[int] = None
    high: Optional[int] = None

    def mutate(self, x: np.ndarray, context: Optional[dict] = None) -> np.ndarray:
        mutated = x + np.random.normal(0.0, self.sigma, size=x.shape)
        if self.low is not None and self.high is not None:
            return np.clip(np.round(mutated), self.low, self.high).astype(int)

        if context and "bounds" in context:
            low_f, high_f = _get_bounds(None, context)
            low = np.floor(low_f)
            high = np.ceil(high_f)
            return np.clip(np.round(mutated), low, high).astype(int)
        if context and "problem" in context:
            low_f, high_f = _get_bounds(context["problem"], context)
            low = np.floor(low_f)
            high = np.ceil(high_f)
            return np.clip(np.round(mutated), low, high).astype(int)

        return np.round(mutated).astype(int)
