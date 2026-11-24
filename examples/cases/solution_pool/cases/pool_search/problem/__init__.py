"""平坦区域让示例稳定展示停滞触发；不声称证明或逃离局部最优。"""
import numpy as np
from nsgablack.core import BlackBoxProblem


class PlateauProblem(BlackBoxProblem):
    def __init__(self):
        super().__init__(name="pool_plateau", dimension=2,
                         bounds=[(-2., 2.)] * 2, objectives=["squared_distance_outside_plateau"])

    def evaluate(self, candidate):
        return max(0., float(np.sum(np.asarray(candidate) ** 2)) - 1.)


def build_problem():
    return PlateauProblem()
