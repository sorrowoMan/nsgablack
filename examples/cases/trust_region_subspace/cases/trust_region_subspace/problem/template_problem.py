# -*- coding: utf-8 -*-
# Problem template: copy and rename for new problems.

from __future__ import annotations

import numpy as np

from nsgablack.core.base import BlackBoxProblem


class ProblemTemplate(BlackBoxProblem):
    # Minimal runnable problem template.

    def __init__(self, dimension: int = 8) -> None:
        bounds = {f"x{i}": [-5.0, 5.0] for i in range(dimension)}
        super().__init__(
            name="ProblemTemplate",
            dimension=dimension,
            bounds=bounds,
            objectives=["obj_0", "obj_1"],
        )

    def evaluate(self, candidate: np.ndarray) -> np.ndarray:
        arr = np.asarray(candidate, dtype=float).reshape(-1)
        obj_0 = float(np.sum(arr ** 2))
        obj_1 = float(np.sum(np.abs(arr)))
        return np.array([obj_0, obj_1], dtype=float)

    def evaluate_constraints(self, candidate: np.ndarray) -> np.ndarray:
        _ = candidate
        return np.zeros(0, dtype=float)
