"""二维平方和：候选、目标和问题边界均在本 Case 内明确。"""
import numpy as np
from nsgablack.core import BlackBoxProblem


class FixedPointProblem(BlackBoxProblem):
    def __init__(self):
        super().__init__(name="fixed_point", dimension=2,
                         bounds=[(0.0, 1.0), (0.0, 1.0)],
                         objectives=["squared_norm"])

    def evaluate(self, x):
        return float(np.sum(np.asarray(x, dtype=float) ** 2))


def build_problem():
    return FixedPointProblem()
