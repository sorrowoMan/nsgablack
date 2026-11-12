"""一维双目标问题，便于逐方向核对；原目标永不被标量覆盖。"""
import numpy as np
from nsgablack.core import BlackBoxProblem


class TwoTargets(BlackBoxProblem):
    def __init__(self):
        super().__init__(name="two_targets", dimension=1, objectives=["min", "min"],
                         bounds={"x": (-2.0, 2.0)})

    def evaluate(self, candidate):
        x = float(np.asarray(candidate).reshape(-1)[0])
        return [(x - 1.0) ** 2, (x + 1.0) ** 2]

    def evaluate_constraints(self, candidate):
        x = float(np.asarray(candidate).reshape(-1)[0])
        return [max(0.0, abs(x) - 2.0)]


def build_problem():
    return TwoTargets()
