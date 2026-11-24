import numpy as np
from nsgablack.core import BlackBoxProblem


class NoisySphere(BlackBoxProblem):
    def __init__(self):
        super().__init__(name="noisy_sphere", dimension=2, bounds=[(-2, 2)] * 2,
                         objectives=["scenario_loss"])

    def evaluate(self, x):
        x = np.asarray(x)
        return float(np.sum(x ** 2) + (0.1 + np.linalg.norm(x)) * np.random.normal())
