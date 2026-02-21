"""
Permutation and random-key representations.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Any

import numpy as np

from .base import RepresentationComponentContract
from ..utils.context.context_keys import KEY_DISTANCE_MATRIX


class RandomKeyPermutationDecoder(RepresentationComponentContract):
    context_requires = ()
    context_provides = ()
    context_mutates = ()
    context_cache = ()
    context_notes = ("Random-key encoder/decoder is deterministic; no context I/O.",)

    def decode(self, x: np.ndarray, context: Optional[dict] = None) -> np.ndarray:
        return np.argsort(x)

    def encode(self, x: np.ndarray, context: Optional[dict] = None) -> np.ndarray:
        return np.asarray(x, dtype=float)


@dataclass
class RandomKeyInitializer(RepresentationComponentContract):
    low: float = 0.0
    high: float = 1.0
    context_requires = ()
    context_provides = ()
    context_mutates = ()
    context_cache = ()
    context_notes = ("Random-key initializer uses constructor bounds only; no context I/O.",)

    def __post_init__(self) -> None:
        self._rng = np.random.default_rng()

    def initialize(self, problem: Any, context: Optional[dict] = None) -> np.ndarray:
        return self._rng.uniform(self.low, self.high, problem.dimension)


@dataclass
class RandomKeyMutation(RepresentationComponentContract):
    sigma: float = 0.1
    low: float = 0.0
    high: float = 1.0
    context_requires = ()
    context_provides = ()
    context_mutates = ()
    context_cache = ()
    context_notes = ("Random-key mutation uses local sigma/bounds; no context I/O.",)

    def __post_init__(self) -> None:
        self._rng = np.random.default_rng()

    def mutate(self, x: np.ndarray, context: Optional[dict] = None) -> np.ndarray:
        mutated = x + self._rng.normal(0.0, self.sigma, size=x.shape)
        return np.clip(mutated, self.low, self.high)


@dataclass
class PermutationInitializer(RepresentationComponentContract):
    context_requires = ()
    context_provides = ()
    context_mutates = ()
    context_cache = ()
    context_notes = ("Permutation initializer uses problem dimension only; no context I/O.",)

    def __post_init__(self) -> None:
        self._rng = np.random.default_rng()

    def initialize(self, problem: Any, context: Optional[dict] = None) -> np.ndarray:
        n = problem.dimension
        perm = np.arange(n)
        self._rng.shuffle(perm)
        return perm.astype(int)


@dataclass
class PermutationSwapMutation(RepresentationComponentContract):
    context_requires = ()
    context_provides = ()
    context_mutates = ()
    context_cache = ()
    context_notes = ("Swap mutation is stateless; no context I/O.",)

    def __post_init__(self) -> None:
        self._rng = np.random.default_rng()

    def mutate(self, x: np.ndarray, context: Optional[dict] = None) -> np.ndarray:
        if len(x) < 2:
            return x
        i, j = self._rng.choice(len(x), size=2, replace=False)
        mutated = np.array(x, copy=True)
        mutated[i], mutated[j] = mutated[j], mutated[i]
        return mutated


@dataclass
class PermutationInversionMutation(RepresentationComponentContract):
    context_requires = ()
    context_provides = ()
    context_mutates = ()
    context_cache = ()
    context_notes = ("Inversion mutation is stateless; no context I/O.",)

    def __post_init__(self) -> None:
        self._rng = np.random.default_rng()

    def mutate(self, x: np.ndarray, context: Optional[dict] = None) -> np.ndarray:
        if len(x) < 2:
            return x
        i, j = np.sort(self._rng.choice(len(x), size=2, replace=False))
        mutated = np.array(x, copy=True)
        mutated[i:j] = mutated[i:j][::-1]
        return mutated


@dataclass
class PermutationRepair(RepresentationComponentContract):
    context_requires = ()
    context_provides = ()
    context_mutates = ()
    context_cache = ()
    context_notes = ("Repair uses rank-based projection only; no context I/O.",)

    def __post_init__(self) -> None:
        self._rng = np.random.default_rng()

    def repair(self, x: np.ndarray, context: Optional[dict] = None) -> np.ndarray:
        x = np.asarray(x)
        n = len(x)
        if n == 0:
            return x
        noise = self._rng.random(size=n) * 1e-6
        return np.argsort(x + noise)


@dataclass
class PermutationFixRepair(RepresentationComponentContract):
    context_requires = ()
    context_provides = ()
    context_mutates = ()
    context_cache = ()
    context_notes = ("Duplicate/missing value fix is local; no context I/O.",)

    def repair(self, x: np.ndarray, context: Optional[dict] = None) -> np.ndarray:
        arr = np.round(np.asarray(x)).astype(int)
        n = len(arr)
        if n == 0:
            return arr
        arr = np.clip(arr, 0, n - 1)
        missing = [i for i in range(n) if i not in arr]
        seen = set()
        for idx, val in enumerate(arr):
            if val in seen:
                arr[idx] = missing.pop(0)
            else:
                seen.add(val)
        return arr


@dataclass
class TwoOptMutation(RepresentationComponentContract):
    max_iters: int = 1
    context_requires = ()
    context_provides = ()
    context_mutates = ()
    context_cache = ()
    context_notes = ("Optionally uses distance matrix from context for accepted-improvement 2-opt.",)

    def __post_init__(self) -> None:
        self._rng = np.random.default_rng()

    def mutate(self, x: np.ndarray, context: Optional[dict] = None) -> np.ndarray:
        perm = np.array(x, copy=True).astype(int)
        n = len(perm)
        if n < 4:
            return perm

        dist = context.get(KEY_DISTANCE_MATRIX) if context else None
        for _ in range(self.max_iters):
            i, j = np.sort(self._rng.choice(n, size=2, replace=False))
            if i == 0 and j == n - 1:
                continue
            cand = perm.copy()
            cand[i:j] = cand[i:j][::-1]
            if dist is None:
                perm = cand
            else:
                if _tour_distance(cand, dist) < _tour_distance(perm, dist):
                    perm = cand
        return perm


@dataclass
class OrderCrossover(RepresentationComponentContract):
    context_requires = ()
    context_provides = ()
    context_mutates = ()
    context_cache = ()
    context_notes = ("OX crossover uses parent permutations only; no context I/O.",)

    def __post_init__(self) -> None:
        self._rng = np.random.default_rng()

    def crossover(self, parent1: np.ndarray, parent2: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        n = len(parent1)
        i, j = np.sort(self._rng.choice(n, size=2, replace=False))
        child1 = _order_child(parent1, parent2, i, j)
        child2 = _order_child(parent2, parent1, i, j)
        return child1, child2


@dataclass
class PMXCrossover(RepresentationComponentContract):
    context_requires = ()
    context_provides = ()
    context_mutates = ()
    context_cache = ()
    context_notes = ("PMX crossover uses parent permutations only; no context I/O.",)

    def __post_init__(self) -> None:
        self._rng = np.random.default_rng()

    def crossover(self, parent1: np.ndarray, parent2: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        n = len(parent1)
        i, j = np.sort(self._rng.choice(n, size=2, replace=False))
        child1 = _pmx_child(parent1, parent2, i, j)
        child2 = _pmx_child(parent2, parent1, i, j)
        return child1, child2


def _tour_distance(perm: np.ndarray, dist: np.ndarray) -> float:
    total = 0.0
    for i in range(len(perm)):
        j = (i + 1) % len(perm)
        total += dist[perm[i], perm[j]]
    return float(total)


def _order_child(p1: np.ndarray, p2: np.ndarray, i: int, j: int) -> np.ndarray:
    n = len(p1)
    child = -np.ones(n, dtype=int)
    child[i:j] = p1[i:j]
    fill = [x for x in p2 if x not in child]
    idx = 0
    for k in list(range(0, i)) + list(range(j, n)):
        child[k] = fill[idx]
        idx += 1
    return child


def _pmx_child(p1: np.ndarray, p2: np.ndarray, i: int, j: int) -> np.ndarray:
    n = len(p1)
    child = -np.ones(n, dtype=int)
    child[i:j] = p1[i:j]
    for k in range(i, j):
        if p2[k] not in child:
            val = p2[k]
            pos = k
            while True:
                # 查找p1[pos]在p2中的位置
                positions = np.where(p2 == p1[pos])[0]
                if len(positions) == 0:
                    # 元素不在p2中，跳过或复制
                    if child[pos] == -1:
                        child[pos] = val
                    break
                pos = int(positions[0])
                if child[pos] == -1:
                    child[pos] = val
                    break
    for k in range(n):
        if child[k] == -1:
            child[k] = p2[k]
    return child
