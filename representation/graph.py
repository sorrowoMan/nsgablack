"""
Graph-oriented representation helpers.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np

from .base import RepresentationComponentContract
from ..utils.context.context_keys import KEY_NUM_NODES


@dataclass
class GraphEdgeInitializer(RepresentationComponentContract):
    num_nodes: Optional[int] = None
    density: float = 0.1
    context_requires = (KEY_NUM_NODES,)
    context_provides = ()
    context_mutates = ()
    context_cache = ()
    context_notes = ("Reads number of graph nodes from context when problem metadata is absent.",)

    def __post_init__(self) -> None:
        self._rng = np.random.default_rng()

    def initialize(self, problem, context: Optional[dict] = None) -> np.ndarray:
        if self.num_nodes is None:
            n = getattr(problem, "num_nodes", None)
            if n is None and context:
                n = context.get(KEY_NUM_NODES)
            if n is None:
                n = problem.dimension
        else:
            n = self.num_nodes

        edge_count = n * (n - 1) // 2
        return (self._rng.random(edge_count) < self.density).astype(int)


@dataclass
class GraphEdgeMutation(RepresentationComponentContract):
    rate: float = 0.02
    context_requires = ()
    context_provides = ()
    context_mutates = ()
    context_cache = ()
    context_notes = ("Edge-flip mutation is stateless; no context I/O.",)

    def __post_init__(self) -> None:
        self._rng = np.random.default_rng()

    def mutate(self, x: np.ndarray, context: Optional[dict] = None) -> np.ndarray:
        mutated = np.array(x, copy=True)
        mask = self._rng.random(len(mutated)) < self.rate
        mutated[mask] = 1 - mutated[mask]
        return mutated


def _edge_index_to_pair(idx: int, n: int) -> tuple[int, int]:
    count = 0
    for i in range(n):
        for j in range(i + 1, n):
            if count == idx:
                return i, j
            count += 1
    return 0, 1


def _pair_to_edge_index(i: int, j: int, n: int) -> int:
    if i > j:
        i, j = j, i
    idx = 0
    for a in range(n):
        for b in range(a + 1, n):
            if a == i and b == j:
                return idx
            idx += 1
    return -1


@dataclass
class GraphConnectivityRepair(RepresentationComponentContract):
    context_requires = (KEY_NUM_NODES,)
    context_provides = ()
    context_mutates = ()
    context_cache = ()
    context_notes = ("Repairs connectivity using num_nodes from context.",)

    def __post_init__(self) -> None:
        self._rng = np.random.default_rng()

    def repair(self, x: np.ndarray, context: Optional[dict] = None) -> np.ndarray:
        n = context.get(KEY_NUM_NODES) if context else None
        if n is None:
            raise ValueError("num_nodes is required in context for graph repair")
        vec = np.array(x, copy=True).astype(int)
        adj = np.zeros((n, n), dtype=int)
        for idx, val in enumerate(vec):
            if val > 0:
                i, j = _edge_index_to_pair(idx, n)
                adj[i, j] = 1
                adj[j, i] = 1

        # find components
        visited = set()
        comps = []
        for i in range(n):
            if i in visited:
                continue
            stack = [i]
            comp = []
            while stack:
                u = stack.pop()
                if u in visited:
                    continue
                visited.add(u)
                comp.append(u)
                neighbors = np.where(adj[u] > 0)[0].tolist()
                stack.extend(neighbors)
            comps.append(comp)

        if len(comps) <= 1:
            return vec

        # connect components with random edges
        for c_idx in range(len(comps) - 1):
            a = self._rng.choice(comps[c_idx])
            b = self._rng.choice(comps[c_idx + 1])
            e_idx = _pair_to_edge_index(a, b, n)
            if e_idx >= 0:
                vec[e_idx] = 1
        return vec


@dataclass
class GraphDegreeRepair(RepresentationComponentContract):
    min_degree: int = 1
    max_degree: Optional[int] = None
    context_requires = (KEY_NUM_NODES,)
    context_provides = ()
    context_mutates = ()
    context_cache = ()
    context_notes = ("Repairs graph node degree constraints using num_nodes from context.",)

    def __post_init__(self) -> None:
        self._rng = np.random.default_rng()

    def repair(self, x: np.ndarray, context: Optional[dict] = None) -> np.ndarray:
        n = context.get(KEY_NUM_NODES) if context else None
        if n is None:
            raise ValueError("num_nodes is required in context for graph repair")
        vec = np.array(x, copy=True).astype(int)
        adj = np.zeros((n, n), dtype=int)
        for idx, val in enumerate(vec):
            if val > 0:
                i, j = _edge_index_to_pair(idx, n)
                adj[i, j] = 1
                adj[j, i] = 1

        degrees = np.sum(adj, axis=1)
        max_deg = self.max_degree if self.max_degree is not None else n - 1

        # reduce degrees over max
        for i in range(n):
            while degrees[i] > max_deg:
                neighbors = np.where(adj[i] > 0)[0]
                if neighbors.size == 0:
                    break
                j = int(self._rng.choice(neighbors))
                adj[i, j] = 0
                adj[j, i] = 0
                degrees[i] -= 1
                degrees[j] -= 1

        # increase degrees below min
        for i in range(n):
            while degrees[i] < self.min_degree:
                candidates = [j for j in range(n) if j != i and adj[i, j] == 0]
                if len(candidates) == 0:
                    break
                j = int(self._rng.choice(candidates))
                adj[i, j] = 1
                adj[j, i] = 1
                degrees[i] += 1
                degrees[j] += 1

        # rebuild vector
        idx = 0
        for a in range(n):
            for b in range(a + 1, n):
                vec[idx] = adj[a, b]
                idx += 1
        return vec
