"""SA 求解各向异性二次谷地，最优点 [-1.5, 0.75]。"""
import numpy as np
from nsgablack.core import BlackBoxProblem
from nsgablack.units.contracts import candidate_array


class ValleyProblem(BlackBoxProblem):
    optimum = (-1.5, 0.75)

    def __init__(self):
        super().__init__(name="SA 二维谷地", dimension=2, objectives=["minimize"],
                         bounds={"x0": (-4.0, 4.0), "x1": (-4.0, 4.0)})

    def evaluate(self, candidate):
        x = candidate_array(candidate)
        return float((x[0] + 1.5) ** 2 + 4.0 * (x[1] - 0.75) ** 2)

    def evaluate_constraints(self, candidate):
        x = candidate_array(candidate)
        return np.maximum(-4.0 - x, 0.0) + np.maximum(x - 4.0, 0.0)
