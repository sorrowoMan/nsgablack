from __future__ import annotations

import numpy as np

from nsgablack.core.base import BlackBoxProblem
from nsgablack.core.evolution_solver import EvolutionSolver


class _Sphere(BlackBoxProblem):
    def __init__(self) -> None:
        super().__init__(name="sphere", dimension=2)

    def evaluate(self, x):
        arr = np.asarray(x, dtype=float)
        return float(np.sum(arr**2))


def test_solver_control_plane_snapshot_and_context_calls() -> None:
    solver = EvolutionSolver(_Sphere(), pop_size=2, max_generations=1)

    pop = np.asarray([[0.0, 0.0], [1.0, 1.0]], dtype=float)
    obj = np.asarray([[0.0], [2.0]], dtype=float)
    vio = np.asarray([0.0, 0.0], dtype=float)

    assert solver.write_population_snapshot(pop, obj, vio) is True
    payload = solver.read_snapshot()
    assert isinstance(payload, dict)
    assert "population" in payload
    ctx = solver.get_context()
    assert "snapshot_key" in ctx


def test_solver_control_plane_updates_state() -> None:
    solver = EvolutionSolver(_Sphere(), pop_size=2, max_generations=1)

    assert solver.set_generation(7) == 7
    assert solver.increment_evaluation_count(3) == 3
    solver.set_best_snapshot(np.asarray([1.0, 2.0]), 5.0)
    solver.set_pareto_snapshot(np.asarray([[1.0, 2.0]]), np.asarray([[5.0]]))

    best_x, best_obj = solver.resolve_best_snapshot()
    assert int(solver.generation) == 7
    assert int(solver.evaluation_count) == 3
    assert best_x is not None
    assert float(best_obj) == 5.0
