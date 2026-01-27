"""
Constraint helpers for representation modules.
"""

from __future__ import annotations

from typing import Any, Tuple
import numpy as np


def _bounds_to_arrays(bounds: Any, dimension: int) -> Tuple[np.ndarray, np.ndarray]:
    arr = np.asarray(bounds, dtype=float)
    if arr.shape[0] != dimension:
        raise ValueError("bounds length must match dimension")
    return arr[:, 0], arr[:, 1]


class BoundConstraint:
    def __init__(self, bounds: Any):
        self.bounds = bounds
        self._low, self._high = _bounds_to_arrays(bounds, len(bounds))

    def check(self, x: np.ndarray) -> bool:
        arr = np.asarray(x, dtype=float)
        return bool(np.all(arr >= self._low) and np.all(arr <= self._high))

    def repair(self, x: np.ndarray) -> np.ndarray:
        arr = np.asarray(x, dtype=float)
        return np.clip(arr, self._low, self._high)
