# -*- coding: utf-8 -*-
"""Example problem: simple two-objective continuous optimization."""

from __future__ import annotations

import numpy as np

from nsgablack.core.base import BlackBoxProblem


class ExampleProblem(BlackBoxProblem):
    def __init__(self, dimension: int = 8) -> None:
        bounds = {f"x{i}": [-5.0, 5.0] for i in range(dimension)}
        super().__init__(
            name="ExampleProblem",
            dimension=dimension,
            bounds=bounds,
            objectives=["sphere", "l1"],
        )

    def evaluate(self, x: np.ndarray) -> np.ndarray:
        arr = np.asarray(x, dtype=float).reshape(-1)
        f1 = float(np.sum(arr ** 2))
        f2 = float(np.sum(np.abs(arr)))
        return np.array([f1, f2], dtype=float)

    def evaluate_constraints(self, x: np.ndarray) -> np.ndarray:
        # No hard constraints in this minimal example.
        return np.zeros(0, dtype=float)
