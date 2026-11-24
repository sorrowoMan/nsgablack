"""两种原料的投料比例；容量是硬约束，均衡偏好另交 Bias。"""
import numpy as np

from nsgablack.core import BlackBoxProblem


def recipe_cost(candidate):
    x = np.asarray(candidate, dtype=float)
    return (x[..., 0] - 0.85) ** 2 + 1.6 * (x[..., 1] - 0.65) ** 2 + 0.03 * x.sum(axis=-1)


class RecipeProblem(BlackBoxProblem):
    def __init__(self):
        super().__init__(name="双原料配方", dimension=2, objectives=["minimize"],
                         bounds=[(0., 1.), (0., 1.)])

    def evaluate(self, candidate):
        return [float(recipe_cost(candidate))]

    def evaluate_constraints(self, candidate):
        x = np.asarray(candidate, dtype=float)
        return np.stack((-x[..., 0], -x[..., 1], x[..., 0] - 1., x[..., 1] - 1.,
                         x.sum(axis=-1) - 1.2), axis=-1)
