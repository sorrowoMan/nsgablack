import numpy as np
from nsgablack.core.base import BlackBoxProblem
class SphereProblem(BlackBoxProblem):
    def __init__(self, dimension=8):
        super().__init__(name="Sphere", dimension=dimension, bounds={f"x{i}":(-5,5) for i in range(dimension)}, objectives=["sphere","l1"])
    def evaluate(self, x):
        a=np.asarray(x);return np.array([float(np.sum(a**2)),float(np.sum(np.abs(a)))],dtype=float)
    def evaluate_constraints(self, x):return np.zeros(0)
