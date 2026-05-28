"""Sphere problem with dynamic repair demo."""
import numpy as np
from nsgablack.core.base import BlackBoxProblem

class SphereProblem(BlackBoxProblem):
    def __init__(self, dimension=6):
        super().__init__(name="Sphere", dimension=dimension,
            bounds={f"x{i}": (-2.0,2.0) for i in range(dimension)}, objectives=["sphere"])
    def evaluate(self, x):
        return np.array([float(np.sum(np.asarray(x)**2))], dtype=float)
    def evaluate_constraints(self, x):
        return np.zeros(0, dtype=float)
