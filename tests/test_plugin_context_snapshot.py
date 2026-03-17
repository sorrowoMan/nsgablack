from __future__ import annotations

import numpy as np

from nsgablack.plugins.base import Plugin
from nsgablack.core.state.context_keys import (
    KEY_CONSTRAINT_VIOLATIONS,
    KEY_OBJECTIVES,
    KEY_POPULATION,
)


class _DummyPlugin(Plugin):
    def __init__(self) -> None:
        super().__init__("dummy")


def test_get_population_snapshot_prefers_adapter_get_population() -> None:
    class _Adapter:
        def get_population(self):
            x = np.array([[1.0, 2.0], [3.0, 4.0]], dtype=float)
            f = np.array([[10.0], [20.0]], dtype=float)
            v = np.array([0.0, 1.0], dtype=float)
            return x, f, v

    class _Solver:
        adapter = _Adapter()
        population = np.array([[9.0, 9.0]], dtype=float)
        objectives = np.array([[99.0]], dtype=float)
        constraint_violations = np.array([9.0], dtype=float)

    plugin = _DummyPlugin()
    x, f, v = plugin.get_population_snapshot(_Solver())
    assert x.shape == (2, 2)
    assert f.shape == (2, 1)
    assert v.shape == (2,)
    assert float(f[0, 0]) == 10.0


def test_get_population_snapshot_prefers_solver_snapshot() -> None:
    class _Solver:
        def read_snapshot(self, _key=None):
            return {
                KEY_POPULATION: np.array([[5.0, 6.0]], dtype=float),
                KEY_OBJECTIVES: np.array([[7.0]], dtype=float),
                KEY_CONSTRAINT_VIOLATIONS: np.array([0.0], dtype=float),
            }

    plugin = _DummyPlugin()
    x, f, v = plugin.get_population_snapshot(_Solver())
    assert x.shape == (1, 2)
    assert f.shape == (1, 1)
    assert v.shape == (1,)
    assert float(x[0, 0]) == 5.0


def test_get_population_snapshot_falls_back_to_solver_state() -> None:
    class _Solver:
        population = np.array([[2.0, 3.0]], dtype=float)
        objectives = np.array([[4.0]], dtype=float)
        constraint_violations = np.array([0.0], dtype=float)

    plugin = _DummyPlugin()
    x, f, v = plugin.get_population_snapshot(_Solver())
    assert x.shape == (1, 2)
    assert f.shape == (1, 1)
    assert v.shape == (1,)
    assert float(x[0, 0]) == 2.0


def test_commit_population_snapshot_uses_adapter_setter() -> None:
    class _Adapter:
        def __init__(self):
            self.calls = 0
            self.payload = None

        def set_population(self, population, objectives, violations):
            self.calls += 1
            self.payload = (
                np.asarray(population, dtype=float),
                np.asarray(objectives, dtype=float),
                np.asarray(violations, dtype=float).reshape(-1),
            )
            return True

    class _Solver:
        def __init__(self):
            self.adapter = _Adapter()
            self.population = None
            self.objectives = None
            self.constraint_violations = None

    plugin = _DummyPlugin()
    solver = _Solver()
    ok = plugin.commit_population_snapshot(
        population=np.array([[1.0, 2.0]], dtype=float),
        objectives=np.array([[3.0]], dtype=float),
        violations=np.array([0.0], dtype=float),
        solver=solver,
    )
    assert ok is True
    assert solver.adapter.calls == 1
    px, pf, pv = solver.adapter.payload
    assert px.shape == (1, 2)
    assert pf.shape == (1, 1)
    assert pv.shape == (1,)
