"""候选表示与稀疏可行性管线。"""
from __future__ import annotations
from typing import Any, Dict, Iterable, Sequence
import numpy as np
from nsgablack.representation.base import RepresentationComponentContract

class SparseBinaryInitializer(RepresentationComponentContract):
    context_requires = ()
    context_provides = ()
    context_mutates = ()
    context_cache = ()
    context_notes = "Initializes a sparse mask from Problem dimension and configured cardinality."

    def __init__(self, max_active: int = 8, seed: int = 7) -> None:
        self.max_active = max(1, int(max_active))
        self._rng = np.random.default_rng(int(seed))

    def initialize(self, problem, context: Dict[str, Any] | None = None) -> np.ndarray:
        _ = context
        dim = int(getattr(problem, "dimension", 1))
        cap = max(1, min(self.max_active, dim))
        k = int(self._rng.integers(1, cap + 1))
        idx = self._rng.choice(dim, size=k, replace=False)
        out = np.zeros((dim,), dtype=float)
        out[idx] = 1.0
        return out


class SparseBinaryMutation(RepresentationComponentContract):
    context_requires = ()
    context_provides = ()
    context_mutates = ()
    context_cache = ()
    context_notes = "Flips mask bits using the configured probability; no context keys."

    def __init__(self, flip_prob: float = 0.05, seed: int = 11) -> None:
        self.flip_prob = max(0.0, min(1.0, float(flip_prob)))
        self._rng = np.random.default_rng(int(seed))

    def mutate(self, x: np.ndarray, context: Dict[str, Any] | None = None) -> np.ndarray:
        _ = context
        arr = np.asarray(x, dtype=float).reshape(-1)
        if arr.size == 0:
            return arr
        bits = arr >= 0.5
        flips = self._rng.random(arr.size) < self.flip_prob
        bits[flips] = ~bits[flips]
        return bits.astype(float)


class SparseBinaryRepair(RepresentationComponentContract):
    context_requires = ()
    context_provides = ()
    context_mutates = ()
    context_cache = ()
    context_notes = "Repairs a mask to the configured cardinality without context state."

    def __init__(self, max_active: int = 8) -> None:
        self.max_active = max(1, int(max_active))

    def repair(self, x: np.ndarray, context: Dict[str, Any] | None = None) -> np.ndarray:
        _ = context
        arr = np.asarray(x, dtype=float).reshape(-1)
        arr = np.nan_to_num(arr, nan=0.0, posinf=1.0, neginf=0.0)
        arr = np.clip(arr, 0.0, 1.0)
        mask = arr >= 0.5
        if int(np.sum(mask)) <= self.max_active:
            return mask.astype(float)
        keep = np.argpartition(arr, -self.max_active)[-self.max_active :]
        out = np.zeros_like(arr, dtype=float)
        out[keep] = 1.0
        return out

