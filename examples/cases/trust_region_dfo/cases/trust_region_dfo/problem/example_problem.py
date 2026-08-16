"""Sphere problem with Trust Region DFO adapter.

Migrated from _misc_examples/trust_region_dfo_demo.py.
Demonstrates alternative adapter (TrustRegionDFOAdapter instead of default NSGA2).
"""

import numpy as np

from nsgablack.core.base import BlackBoxProblem


class SphereProblem(BlackBoxProblem):
    def __init__(self, dimension: int = 8):
        super().__init__(
            name="Sphere",
            dimension=dimension,
            bounds={f"x{i}": (-5.0, 5.0) for i in range(dimension)},
            objectives=["sphere"],
        )

    def evaluate(self, candidate: np.ndarray) -> np.ndarray:
        return np.array([float(np.sum(np.asarray(candidate, dtype=float) ** 2))], dtype=float)

    def evaluate_constraints(self, candidate: np.ndarray) -> np.ndarray:
        return np.zeros(0, dtype=float)
