"""Build the second independently runnable optimization Case."""

from __future__ import annotations

import numpy as np

from nsgablack.core.base import BlackBoxProblem
from nsgablack.core.evolution_solver import EvolutionSolver


class ShiftedSphereProblem(BlackBoxProblem):
    def __init__(self) -> None:
        super().__init__(
            name="project_demo_shifted_sphere",
            dimension=2,
            bounds={"x0": (-5.0, 5.0), "x1": (-5.0, 5.0)},
            objectives=["shifted_sum_squares"],
        )

    def evaluate(self, candidate):
        values = np.asarray(candidate, dtype=float) - 1.0
        return np.asarray([float(np.sum(values**2))])


def build_solver(config=None, *, resource_context=None, component_overrides=None):
    del config
    overrides = dict(component_overrides or {})
    solver = EvolutionSolver(
        ShiftedSphereProblem(),
        pop_size=int(overrides.get("pop_size", 8)),
        max_generations=int(overrides.get("max_generations", 2)),
        resource_context=resource_context,
    )
    solver.enable_progress_log = False
    return solver
