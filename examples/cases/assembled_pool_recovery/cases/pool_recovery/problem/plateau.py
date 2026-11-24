"""A real flat objective region makes a short, reproducible stagnation demo."""
import numpy as np
from nsgablack.core import BlackBoxProblem
from nsgablack.units.contracts import candidate_array


class PlateauProblem(BlackBoxProblem):
    def __init__(self):
        super().__init__(name="二维平坦区域恢复演示", dimension=2, objectives=["minimize"],
                         bounds={"x0": (-2.0, 2.0), "x1": (-2.0, 2.0)})

    def evaluate(self, candidate):
        x = candidate_array(candidate)
        return max(0.0, float(np.dot(x, x)) - 1.0)

    def evaluate_constraints(self, candidate):
        x = candidate_array(candidate)
        return np.maximum(-2.0 - x, 0.0) + np.maximum(x - 2.0, 0.0)


def build_problem():
    return PlateauProblem()
