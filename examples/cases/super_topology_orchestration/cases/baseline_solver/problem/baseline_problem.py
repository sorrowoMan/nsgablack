"""Small numerical baseline used by the parallel Project stage."""

from __future__ import annotations

import numpy as np

from nsgablack.core import BlackBoxProblem


class BaselineOptimizationProblem(BlackBoxProblem):
    def __init__(self) -> None:
        super().__init__(
            name="baseline_quadratic",
            dimension=1,
            bounds={"x0": [0.0, 1.0]},
            objectives=("squared_error",),
        )

    def evaluate(self, candidate, context=None):
        del context
        x = float(np.asarray(candidate, dtype=float).reshape(-1)[0])
        return np.asarray([(x - 0.25) ** 2], dtype=float)
