"""
Tabu Search bias.

This bias penalizes proximity to proposals admitted by committed search steps.
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

    Scoring is read-only. ``record_accepted`` advances memory inside the owning
    search step transaction; evaluation alone never records a visit.
    """
    context_requires = ()
    requires_metrics = ()
    context_provides = ()
    context_mutates = ()
    context_cache = ()
    context_notes = "Scores against committed admitted-candidate memory; evaluation is read-only."
    cacheable = False
    objective_independent = True
    stateful_preference = True
    state_recovery_level = "L1"
    state_recovery_notes = "Restores token-aligned admitted-proposal memory and validates memory policy."



    weight: float = 0.15
    tabu_size: int = 30
    distance_threshold: float = 0.1
    penalty_scale: float = 0.5
    name: str = field(default="tabu_search_bias", init=False)

    def __post_init__(self):
        super().__init__(self.name, self.weight, adaptive=False)
        self._tabu_list: List[np.ndarray] = []
        self._tabu_tokens: List[str] = []

    def compute(self, x: np.ndarray, context: OptimizationContext) -> float:
        if not self._tabu_list:
            return 0.0

        distances = [np.linalg.norm(x - t) for t in self._tabu_list]
        min_dist = float(np.min(distances)) if len(distances) > 0 else float("inf")

        if min_dist >= self.distance_threshold:
            return 0.0
        # Penalize being too close to tabu points
        return self.penalty_scale * (1.0 - min_dist / max(self.distance_threshold, 1e-9))

    def record_accepted(self, candidates):
        if self.tabu_size < 1:
            raise ValueError("tabu_size must be positive")
        for x, token in zip(candidates.numeric_matrix, candidates.candidate_tokens):
            if not isinstance(token, str) or not token:
                raise ValueError("Tabu memory requires admitted candidate tokens")
            if token in self._tabu_tokens:
                continue
            self._tabu_list.append(np.array(x, copy=True))
            self._tabu_tokens.append(token)
            if len(self._tabu_list) > self.tabu_size:
                self._tabu_list.pop(0)
                self._tabu_tokens.pop(0)

    def get_state(self):
        return {"schema": "nsgablack.tabu_memory/v1", "policy": "committed_admitted_proposals",
                "config": [self.tabu_size, self.distance_threshold, self.penalty_scale],
                "tokens": list(self._tabu_tokens), "candidates": [x.tolist() for x in self._tabu_list]}

    def reset_run_state(self):
        self._tabu_list, self._tabu_tokens = [], []

    def set_state(self, state):
        if (state.get("schema") != "nsgablack.tabu_memory/v1" or
                state.get("policy") != "committed_admitted_proposals" or
                state.get("config") != [self.tabu_size, self.distance_threshold, self.penalty_scale]):
            raise ValueError("Tabu checkpoint policy/configuration mismatch")
        tokens = list(state["tokens"])
        values = [np.asarray(x, dtype=float) for x in state["candidates"]]
        if (len(tokens) != len(values) or len(tokens) > self.tabu_size or len(set(tokens)) != len(tokens)
                or any(not isinstance(t, str) or not t for t in tokens)
                or any(x.ndim != 1 or not np.all(np.isfinite(x)) for x in values)
                or (values and any(x.shape != values[0].shape for x in values))):
            raise ValueError("Invalid Tabu memory checkpoint")
        self._tabu_tokens, self._tabu_list = tokens, [x.copy() for x in values]


__all__ = ["TabuSearchBias"]
