"""Runnable, small defaults for a newly generated optimization Case."""
import numpy as np
from nsgablack.core import BlackBoxProblem, ComposableSolver
from nsgablack.adapters import NSGA2Adapter


class QuadraticProblem(BlackBoxProblem):
    def __init__(self, dimension=2):
        super().__init__(name="starter_quadratic", dimension=dimension,
                         bounds=[(-2.0, 2.0)] * dimension, objectives=["squared_norm"])

    def evaluate(self, x):
        return float(np.sum(np.asarray(x, dtype=float) ** 2))


def build_starter_solver(*, problem=None, pipeline=None, resource_context=None,
                         component_overrides=None, max_steps=2):
    from nsgablack.project import apply_solver_component_overrides
    solver = ComposableSolver(
        problem=problem if problem is not None else QuadraticProblem(),
        representation_pipeline=pipeline,
        adapter=NSGA2Adapter(population_size=8, offspring_size=8),
        resource_context=resource_context,
    )
    solver.set_max_steps(max_steps)
    apply_solver_component_overrides(solver, component_overrides)
    return solver
