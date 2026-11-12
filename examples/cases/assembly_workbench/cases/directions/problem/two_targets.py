"""双目标始终属于 Problem；方向视图只改变局部搜索的比较含义。"""
import numpy as np
from nsgablack.core import BlackBoxProblem


class DirectionProblem(BlackBoxProblem):
    def __init__(self):
        super().__init__(name="direction_targets", dimension=1, objectives=["min", "min"],
                         bounds={"x": (-2.0, 2.0)})

    def evaluate(self, candidate):
        x = float(np.asarray(candidate).reshape(-1)[0])
        return [(x - 1.0) ** 2, (x + 1.0) ** 2]

    def evaluate_constraints(self, candidate):
        return [max(0.0, abs(float(np.asarray(candidate).reshape(-1)[0])) - 2.0)]


def build_problem():
    return DirectionProblem()
