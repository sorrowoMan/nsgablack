# -*- coding: utf-8 -*-
# Example adapter (simple random proposer).

from __future__ import annotations

from typing import Any, Dict, Sequence

import numpy as np

from nsgablack.adapters.algorithm_adapter import AlgorithmAdapter


class ExampleAdapter(AlgorithmAdapter):
    def __init__(self, max_candidates: int = 8, seed: int = 0) -> None:
        super().__init__(name="example_adapter")
        self.max_candidates = max(1, int(max_candidates))
        self._rng = np.random.default_rng(int(seed))

    def propose(self, solver: Any, context: Dict[str, Any]) -> Sequence[np.ndarray]:
        _ = context
        dim = int(getattr(getattr(solver, "problem", None), "dimension", 1))
        out = []
        for _ in range(self.max_candidates):
            out.append(self._rng.uniform(-1.0, 1.0, size=(dim,)))
        return out
