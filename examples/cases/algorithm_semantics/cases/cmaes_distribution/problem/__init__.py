import numpy as np
from nsgablack.core import BlackBoxProblem


class QuadraticProblem(BlackBoxProblem):
    def __init__(self, dimension=2):
        super().__init__(name="cma_quadratic", dimension=dimension,
            objectives=["min"], bounds=[(-100., 100.)] * dimension)
        self.target = np.array([1.]) if dimension == 1 else np.array([.2, -.1])
        self.calls = []

    def evaluate(self, candidate):
        values = np.asarray(candidate, dtype=float)
        self.calls.append(values.copy())
        return [float(np.sum((values - self.target) ** 2))]
