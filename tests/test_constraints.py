import numpy as np

from nsgablack.core.base import BlackBoxProblem
from nsgablack.core.evolution_solver import EvolutionSolver


class BrokenConstraintProblem(BlackBoxProblem):
    def __init__(self, dimension=2):
        bounds = {f"x{i}": (-5, 5) for i in range(dimension)}
        super().__init__(dimension=dimension, objectives=["minimize"], bounds=bounds)

    def evaluate(self, candidate):
        return float(np.sum(np.asarray(candidate, dtype=float) ** 2))

    def evaluate_constraints(self, candidate):
        raise RuntimeError("constraint failure")


def test_constraint_failures_are_handled():
    problem = BrokenConstraintProblem()
    solver = EvolutionSolver(problem)
    solver.pop_size = 4
    solver.initialize_population()
    assert np.isinf(solver.constraint_violations).all()
