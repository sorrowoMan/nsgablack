"""Minimal problem for pooled COPT backend handoff demo.

Actual evaluation is handled by the L4 CoptHandoffProvider.
The Problem is a fallback path (not used when the provider is active).
"""

from __future__ import annotations

import numpy as np

from nsgablack.core.base import BlackBoxProblem


class PooledHandoffProblem(BlackBoxProblem):
    def __init__(self, dimension: int = 3) -> None:
        bounds = {f"x{i}": [-5.0, 5.0] for i in range(dimension)}
        super().__init__(
            name="PooledHandoff",
            dimension=dimension,
            bounds=bounds,
            objectives=["sphere"],
        )

    def evaluate(self, x: np.ndarray) -> np.ndarray:
        arr = np.asarray(x, dtype=float).reshape(-1)
        f1 = float(np.sum(arr * arr))
        return np.array([f1], dtype=float)

    def evaluate_constraints(self, x: np.ndarray) -> np.ndarray:
        return np.zeros(0, dtype=float)
