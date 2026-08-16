"""High-dimensional Sphere problem (20D) for subspace trust region demo."""
import numpy as np
from nsgablack.core.base import BlackBoxProblem

class SphereProblem(BlackBoxProblem):
    def __init__(self, dimension=20):
        super().__init__(name="Sphere", dimension=dimension,
            bounds={f"x{i}":(-5,5) for i in range(dimension)}, objectives=["sphere"])
    def evaluate(self, candidate):
        return np.array([float(np.sum(np.asarray(candidate)**2))], dtype=float)
    def evaluate_constraints(self, candidate):
        return np.zeros(0, dtype=float)
