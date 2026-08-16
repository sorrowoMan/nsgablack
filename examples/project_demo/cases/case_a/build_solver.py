"""Build the first independently runnable optimization Case."""

from __future__ import annotations

import numpy as np

from nsgablack.core.base import BlackBoxProblem
from nsgablack.core.evolution_solver import EvolutionSolver


class SphereProblem(BlackBoxProblem):
    def __init__(self) -> None:
        super().__init__(
            name="project_demo_sphere",
            dimension=2,
            bounds={"x0": (-5.0, 5.0), "x1": (-5.0, 5.0)},
            objectives=["sum_squares"],
        )

    def evaluate(self, candidate):
        values = np.asarray(candidate, dtype=float)
        return np.asarray([float(np.sum(values**2))])


def build_solver(config=None, *, resource_context=None, component_overrides=None):
    del config
    overrides = dict(component_overrides or {})
    solver = EvolutionSolver(
        SphereProblem(),
        pop_size=int(overrides.get("pop_size", 8)),
        max_generations=int(overrides.get("max_generations", 2)),
        resource_context=resource_context,
    )
    solver.enable_progress_log = False
    return solver
