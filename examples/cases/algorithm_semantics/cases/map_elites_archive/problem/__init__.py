"""质量属于 Problem；行为描述符在 Adapter 组件中显式装配。"""
import numpy as np
from nsgablack.core import BlackBoxProblem


class ArchiveProblem(BlackBoxProblem):
    def __init__(self):
        super().__init__(name="archive_cost", dimension=2, objectives=["min"], bounds=[(0., 1.)]*2)
        self.calls = 0

    def evaluate(self, candidate):
        self.calls += 1
        x = np.asarray(candidate)
        return [(x[0] - .2)**2 + (x[1] - .8)**2]

    def evaluate_constraints(self, candidate):
        x = np.asarray(candidate)
        return [float(np.maximum(-x, 0).sum() + np.maximum(x-1, 0).sum())]


def build_problem():
    return ArchiveProblem()
