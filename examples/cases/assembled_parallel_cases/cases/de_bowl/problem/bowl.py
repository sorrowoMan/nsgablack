"""DE 独立求解二维球面问题，已知最优点 [1, -2]。"""
import numpy as np
from nsgablack.core import BlackBoxProblem
from nsgablack.units.contracts import candidate_array


class BowlProblem(BlackBoxProblem):
    optimum = (1.0, -2.0)

    def __init__(self):
        super().__init__(name="DE 二维球面", dimension=2, objectives=["minimize"],
                         bounds={"x0": (-4.0, 4.0), "x1": (-4.0, 4.0)})

    def evaluate(self, candidate):
        x = candidate_array(candidate)
        return float((x[0] - 1.0) ** 2 + (x[1] + 2.0) ** 2)

    def evaluate_constraints(self, candidate):
        x = candidate_array(candidate)
        return np.maximum(-4.0 - x, 0.0) + np.maximum(x - 4.0, 0.0)
