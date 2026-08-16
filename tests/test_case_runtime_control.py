from __future__ import annotations

import time

import numpy as np
import pytest

from blackbase.resources import CancellationRef, CancellationToken, CaseDeadlineExceeded
from nsgablack.core.base import BlackBoxProblem
from nsgablack.core.blank_solver import SolverBase


class _Sphere(BlackBoxProblem):
    def __init__(self) -> None:
        super().__init__(dimension=1, bounds=[(-1.0, 1.0)], objectives=["min"])

    def evaluate(self, candidate):
        return float(np.sum(np.asarray(candidate, dtype=float) ** 2))


class _SlowSolver(SolverBase):
    def __init__(self) -> None:
        super().__init__(_Sphere())
        self.executed = 0

    def step(self) -> None:
        self.executed += 1
        time.sleep(0.01)


class _TokenRuntime:
    def __init__(self, token: CancellationToken) -> None:
        self.token = token

    def checkpoint(self) -> None:
        self.token.checkpoint()


class _CountingRuntime:
    def __init__(self) -> None:
        self.count = 0

    def checkpoint(self) -> None:
        self.count += 1


def test_solver_deadline_interrupts_a_running_generation_loop() -> None:
    solver = _SlowSolver()
    ref = CancellationRef(backend="memory", deadline_at=time.time() + 0.04)
    solver.set_case_runtime(_TokenRuntime(CancellationToken(ref)))

    with pytest.raises(CaseDeadlineExceeded):
        solver.run(max_steps=100)

    assert 0 < solver.executed < 100


def test_solver_checks_control_around_evaluation_and_before_snapshot_commit() -> None:
    solver = SolverBase(_Sphere())
    runtime = _CountingRuntime()
    solver.set_case_runtime(runtime)

    solver.evaluate_individual(np.asarray([0.5]))
    evaluation_checkpoints = runtime.count
    assert evaluation_checkpoints >= 2

    solver.write_population_snapshot(
        np.asarray([[0.5]]),
        np.asarray([[0.25]]),
        np.asarray([0.0]),
    )
    assert runtime.count > evaluation_checkpoints
