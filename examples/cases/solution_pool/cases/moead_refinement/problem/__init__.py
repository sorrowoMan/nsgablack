"""两个目标保持原始含义；方向投影由 MOEA/D 子池提供。"""
import numpy as np
from nsgablack.core import BlackBoxProblem


class TwoCenters(BlackBoxProblem):
    def __init__(self):
        super().__init__(name="two_centers", dimension=2,
                         objectives=["min", "min"], bounds=[(-2., 2.), (-2., 2.)])

    def evaluate(self, candidate):
        x = np.asarray(candidate)
        return [float(np.sum((x - 1.) ** 2)), float(np.sum((x + 1.) ** 2))]


def build_problem():
    return TwoCenters()
