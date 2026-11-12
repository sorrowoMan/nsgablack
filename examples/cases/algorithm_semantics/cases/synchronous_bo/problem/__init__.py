"""真实评估始终是 f(x)=(x-.25)^2。"""
import numpy as np
from nsgablack.core import BlackBoxProblem


class QuadraticProblem(BlackBoxProblem):
    def __init__(self):
        super().__init__(name="bo_quadratic", dimension=1, objectives=["min"], bounds={"x": (0.0, 1.0)})
        self.calls = []

    def evaluate(self, candidate):
        x = float(np.asarray(candidate).reshape(-1)[0])
        self.calls.append(x)
        return [(x - 0.25) ** 2]

    def evaluate_constraints(self, candidate):
        x = float(np.asarray(candidate).reshape(-1)[0])
        return [max(0.0, -x, x - 1.0)]
