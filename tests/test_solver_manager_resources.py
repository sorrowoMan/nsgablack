from __future__ import annotations

import numpy as np
import pytest
from threading import Barrier, Lock

from nsgablack.core import RegimeSpec, ResourceOffer, ResourceRequest, SolverManager
from nsgablack.core.base import BlackBoxProblem
from nsgablack.core.nested_solver import InnerRuntimeEvaluator


class _Problem(BlackBoxProblem):
    def __init__(self) -> None:
        super().__init__(
            name="p",
            dimension=1,
            bounds={"x0": [-1.0, 1.0]},
            objectives=["f1"],
        )

    def evaluate(self, candidate):
        _ = candidate
        return np.array([0.0], dtype=float)

    def evaluate_constraints(self, candidate):
        _ = candidate
        return np.zeros(0, dtype=float)


class _InnerSolver:
    resource_request = ResourceRequest(threads=2, gpus=0, backend="local")

    def run(self, return_dict: bool = False):
        _ = return_dict
        return {"objective": np.array([0.0], dtype=float), "violation": 0.0, "status": "ok"}


class _OuterSolver:
    def __init__(self, threads: int) -> None:
        self.name = "outer"
        self.dimension = 1
        self.problem = _Problem()
        self.resource_request = ResourceRequest(threads=threads, gpus=0, backend="local")
        self.problem.inner_runtime_evaluator = InnerRuntimeEvaluator(
            solver_factory=lambda outer, req: _InnerSolver(),
            parent_contract="outer.default",
        )

    def run(self, return_dict: bool = False):
        _ = return_dict
        return {"objective": np.array([0.0], dtype=float), "violation": 0.0, "status": "ok"}


def test_solver_manager_nested_resource_ok():
    regimes = [RegimeSpec(name="r1", build_solver=lambda: _OuterSolver(threads=4))]
    mgr = SolverManager(regimes=regimes, offer=ResourceOffer(threads=12, gpus=0, backend="local"))
    out = mgr.run(return_dict=True)
    assert "regimes" in out


def test_solver_manager_nested_resource_over_budget():
    regimes = [RegimeSpec(name="r1", build_solver=lambda: _OuterSolver(threads=4))]
    mgr = SolverManager(regimes=regimes, offer=ResourceOffer(threads=8, gpus=0, backend="local"))
    with pytest.raises(RuntimeError):
        mgr.run(return_dict=True)


def test_solver_manager_parallel_phase_is_actually_concurrent():
    barrier = Barrier(2)
    lock = Lock()
    active = 0
    peak_active = 0

    class ConcurrentSolver:
        resource_request = ResourceRequest(threads=1, gpus=0, backend="local")

        def __init__(self, name: str) -> None:
            self.name = name

        def run(self):
            nonlocal active, peak_active
            with lock:
                active += 1
                peak_active = max(peak_active, active)
            try:
                barrier.wait(timeout=1.0)
                return {"status": "ok"}
            finally:
                with lock:
                    active -= 1

    manager = SolverManager(
        regimes=(
            RegimeSpec(name="a", build_solver=lambda: ConcurrentSolver("a")),
            RegimeSpec(name="b", build_solver=lambda: ConcurrentSolver("b")),
        ),
        offer=ResourceOffer(threads=2, gpus=0, backend="local"),
        mode="parallel",
    )

    result = manager.run()

    assert len(result["regimes"]) == 2
    assert peak_active == 2
