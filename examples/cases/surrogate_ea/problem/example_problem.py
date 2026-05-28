"""Sphere problem with surrogate-assisted evaluation.

Migrated from _misc_examples/surrogate_assisted_ea_demo.py.
Demonstrates L4 SurrogateEvaluationProviderPlugin.
"""

import numpy as np

from nsgablack.core.base import BlackBoxProblem


class SphereProblem(BlackBoxProblem):
    def __init__(self, dimension: int = 10):
        super().__init__(
            name="Sphere",
            dimension=dimension,
            bounds={f"x{i}": (-5.0, 5.0) for i in range(dimension)},
            objectives=["sphere"],
        )

    def evaluate(self, x: np.ndarray) -> np.ndarray:
        return np.array([float(np.sum(np.asarray(x, dtype=float) ** 2))], dtype=float)

    def evaluate_constraints(self, x: np.ndarray) -> np.ndarray:
        return np.zeros(0, dtype=float)
