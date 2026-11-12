"""与MOEA/D Case相同的原始双目标，GA按约束支配与拥挤度留存。"""
import numpy as np
from nsgablack.core import BlackBoxProblem


class TwoCenters(BlackBoxProblem):
    def __init__(self):
        super().__init__(name="two_centers", dimension=2,
                         bounds=[(-2., 2.)] * 2, objectives=["left", "right"])

    def evaluate(self, x):
        x = np.asarray(x, dtype=float)
        return [float(np.sum((x - [-1., 0.]) ** 2)),
                float(np.sum((x - [1., 0.]) ** 2))]


def build_problem():
    return TwoCenters()
