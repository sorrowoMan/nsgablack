"""候选结构示例的问题定义。"""
import numpy as np
from nsgablack.core.base import BlackBoxProblem


class Sphere(BlackBoxProblem):
    def __init__(self):
        super().__init__(dimension=2, bounds={"x0": (-5, 5), "x1": (-5, 5)})

    def evaluate(self, candidate):
        return np.array([np.sum(np.asarray(candidate) ** 2)])
