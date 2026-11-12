"""原始问题：二维单目标，与算法无关。"""
import numpy as np
from nsgablack.core import BlackBoxProblem


class ShiftedSphere(BlackBoxProblem):
    def __init__(self):
        super().__init__(name="shifted_sphere", dimension=2,
                         bounds=[(-2., 2.)] * 2, objectives=["distance"])

    def evaluate(self, x):
        return float(np.sum((np.asarray(x, dtype=float) - np.array([.5, -.5])) ** 2))


def build_problem():
    return ShiftedSphere()
