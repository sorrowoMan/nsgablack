"""NSGA-II on bi-objective sphere — migrated from _misc_examples/nsga2_solver_demo.py.

Demonstrates standard scaffold assembly: problem + representation pipeline + NSGA2 adapter
+ elite retention + benchmark harness + module report.
"""

import numpy as np

from nsgablack.core.base import BlackBoxProblem


class BiObjectiveSphereProblem(BlackBoxProblem):
    def __init__(self, dimension: int = 6):
        bounds = {f"x{i}": (-5.0, 5.0) for i in range(dimension)}
        super().__init__(
            name="BiObjectiveSphere",
            dimension=dimension,
            bounds=bounds,
            objectives=["sphere", "shifted_sphere"],
        )

    def evaluate(self, x: np.ndarray) -> np.ndarray:
        arr = np.asarray(x, dtype=float).reshape(-1)
        f1 = float(np.sum(arr * arr))
        f2 = float(np.sum((arr - 1.5) ** 2))
        return np.array([f1, f2], dtype=float)

    def evaluate_constraints(self, x: np.ndarray) -> np.ndarray:
        return np.zeros(0, dtype=float)
