# -*- coding: utf-8 -*-
"""Example adapter implementation for registry integration."""

from __future__ import annotations

from typing import Any, Dict, Sequence

import numpy as np

from nsgablack.adapters.algorithm_adapter import AlgorithmAdapter


class ExampleAdapter(AlgorithmAdapter):
    """Minimal AlgorithmAdapter example for registry integration."""

    context_requires = ()
    context_provides = ()
    context_mutates = ()
    context_cache = ()
    context_notes = ("Example adapter: generates random candidates.",)

    def __init__(self, alpha: float = 0.8, beta: float = 0.1) -> None:
        super().__init__(name="example_adapter")
        self.alpha = float(alpha)
        self.beta = float(beta)

    def propose(self, solver: Any, context: Dict[str, Any]) -> Sequence[np.ndarray]:
        _ = context
        rng = self.create_local_rng(solver)
        dim = int(getattr(getattr(solver, "problem", None), "dimension", 1))
        size = max(1, int(self.alpha * 10))
        out = []
        for _ in range(size):
            out.append(rng.uniform(-1.0, 1.0, size=(dim,)))
        return out

    def update(
        self,
        solver: Any,
        candidates: Sequence[np.ndarray],
        objectives: np.ndarray,
        violations: np.ndarray,
        context: Dict[str, Any],
    ) -> None:
        _ = solver
        _ = candidates
        _ = objectives
        _ = violations
        _ = context
        return None
