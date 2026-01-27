import numpy as np

from nsgablack.core.base import BlackBoxProblem
from nsgablack.core.solver import BlackBoxSolverNSGAII


class BrokenConstraintProblem(BlackBoxProblem):
    def __init__(self, dimension=2):
        bounds = {f"x{i}": (-5, 5) for i in range(dimension)}
        super().__init__(dimension=dimension, objectives=["minimize"], bounds=bounds)

    def evaluate(self, x):
        return float(np.sum(np.asarray(x, dtype=float) ** 2))

    def evaluate_constraints(self, x):
        raise RuntimeError("constraint failure")


def test_constraint_failures_are_handled():
    problem = BrokenConstraintProblem()
    solver = BlackBoxSolverNSGAII(problem)
    solver.pop_size = 4
    solver.initialize_population()
    assert np.isinf(solver.constraint_violations).all()
