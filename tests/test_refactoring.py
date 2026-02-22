"""Refactoring regression tests (pytest-safe, no side effects on import)."""

from __future__ import annotations

import numpy as np

from nsgablack.core import BlackBoxProblem, BlackBoxSolverNSGAII
from nsgablack.core.interfaces import has_bias_module, has_numba


class SimpleTestProblem(BlackBoxProblem):
    def __init__(self):
        super().__init__(name="SimpleTest", dimension=2)

    def evaluate(self, x):
        return [x[0] ** 2 + x[1] ** 2]


class MockBiasModule:
    def compute_bias(self, x, context):
        return 0.0

    def add_bias(self, bias, weight=1.0, name=None):
        return True

    def is_enabled(self):
        return True

    def enable(self):
        return None

    def disable(self):
        return None


def test_core_import_and_basic_solver_creation():
    problem = SimpleTestProblem()
    solver = BlackBoxSolverNSGAII(problem)
    solver.pop_size = 20
    solver.max_generations = 5
    assert solver.dimension == 2
    assert solver.pop_size == 20
    assert solver.max_generations == 5


def test_dependency_injection_and_backward_compatibility():
    problem = SimpleTestProblem()
    mock_bias = MockBiasModule()
    solver = BlackBoxSolverNSGAII(problem, bias_module=mock_bias)
    assert solver.bias_module is not None
    assert solver.has_bias_support()

    solver.bias_module = mock_bias
    solver.enable_bias = True
    assert solver.enable_bias is True


def test_interface_and_lazy_loading_checks():
    problem = SimpleTestProblem()
    solver = BlackBoxSolverNSGAII(problem)
    # function returns bool and does not raise
    assert isinstance(has_bias_module(), bool)
    assert isinstance(has_numba(), bool)
    assert isinstance(solver.has_bias_support(), bool)
    assert isinstance(solver.has_numba_support(), bool)


def test_solver_runs_small_problem():
    problem = SimpleTestProblem()
    solver = BlackBoxSolverNSGAII(problem)
    solver.pop_size = 16
    solver.max_generations = 3
    best_x, best_f = solver.run(return_dict=False)
    assert best_x is not None
    assert np.isfinite(float(best_f))
