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


def test_runtime_facade_forwards_snapshot_and_context_calls() -> None:
    solver = EvolutionSolver(_Sphere(), pop_size=2, max_generations=1)
    runtime = solver.runtime

    pop = np.asarray([[0.0, 0.0], [1.0, 1.0]], dtype=float)
    obj = np.asarray([[0.0], [2.0]], dtype=float)
    vio = np.asarray([0.0, 0.0], dtype=float)

    assert runtime.write_population_snapshot(pop, obj, vio) is True
    payload = runtime.read_snapshot()
    assert isinstance(payload, dict)
    assert "population" in payload
    ctx = runtime.get_context()
    assert "snapshot_key" in ctx


def test_runtime_facade_forwards_control_plane_updates() -> None:
    solver = EvolutionSolver(_Sphere(), pop_size=2, max_generations=1)
    runtime = solver.runtime

    assert runtime.set_generation(7) == 7
    assert runtime.increment_evaluation_count(3) == 3
    runtime.set_best_snapshot(np.asarray([1.0, 2.0]), 5.0)
    runtime.set_pareto_snapshot(np.asarray([[1.0, 2.0]]), np.asarray([[5.0]]))

    best_x, best_obj = runtime.resolve_best_snapshot()
    assert int(solver.generation) == 7
    assert int(solver.evaluation_count) == 3
    assert best_x is not None
    assert float(best_obj) == 5.0
