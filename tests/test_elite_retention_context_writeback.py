from __future__ import annotations

import numpy as np

from nsgablack.plugins.runtime.elite_retention import BasicElitePlugin


class _Adapter:
    def __init__(self) -> None:
        self.X = np.array([[0.0, 0.0], [10.0, 10.0], [9.0, 9.0]], dtype=float)
        self.F = np.array([[0.0], [20.0], [18.0]], dtype=float)
        self.V = np.array([0.0, 0.0, 0.0], dtype=float)
        self.set_calls = 0

    def get_population(self):
        return self.X, self.F, self.V

    def set_population(self, population, objectives, violations):
        self.set_calls += 1
        self.X = np.asarray(population, dtype=float)
        self.F = np.asarray(objectives, dtype=float)
        self.V = np.asarray(violations, dtype=float).reshape(-1)
        return True


class _Solver:
    def __init__(self) -> None:
        self.adapter = _Adapter()
        self.population = None
        self.objectives = None
        self.constraint_violations = None
        self.dimension = 2
        self.var_bounds = [(-10.0, 10.0), (-10.0, 10.0)]
        self.representation_pipeline = None
        self.generation = 1
        self.evaluation_count = 0

    def evaluate_individual(self, x, individual_id=None):
        _ = individual_id
        x = np.asarray(x, dtype=float)
        self.evaluation_count += 1
        return np.array([float(np.sum(np.abs(x)))], dtype=float), 0.0


def test_basic_elite_plugin_writes_back_via_adapter_set_population() -> None:
    np.random.seed(0)
    solver = _Solver()
    plugin = BasicElitePlugin(retention_prob=1.0, retention_ratio=0.34)
    plugin.attach(solver)
    plugin.on_solver_init(solver)

    X0, F0, V0 = solver.adapter.get_population()
    plugin.on_population_init(X0, F0, V0)
    plugin.on_generation_end(1)

    assert solver.adapter.set_calls >= 1
    X1, F1, V1 = solver.adapter.get_population()
    assert X1.shape == X0.shape
    assert F1.shape == F0.shape
    assert V1.shape == V0.shape
    assert solver.evaluation_count >= 1
