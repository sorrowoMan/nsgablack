# -*- coding: utf-8 -*-
"""
Minimal SolverManager demo:
- single solver (works)
- two solvers with nested inner resource (over budget -> error)
"""

from __future__ import annotations

import numpy as np

from nsgablack.core import (
    EvolutionSolver,
    RegimeSpec,
    ResourceOffer,
    ResourceRequest,
    SolverManager,
)
from nsgablack.core.base import BlackBoxProblem
from nsgablack.core.nested_solver import InnerRuntimeEvaluator


class _Problem(BlackBoxProblem):
    def __init__(self) -> None:
        super().__init__(
            name="p",
            dimension=2,
            bounds={"x0": [-1.0, 1.0], "x1": [-1.0, 1.0]},
            objectives=["f1"],
        )

    def evaluate(self, x):
        arr = np.asarray(x, dtype=float).reshape(-1)
        return np.array([float(np.sum(arr * arr))], dtype=float)

    def evaluate_constraints(self, x):
        _ = x
        return np.zeros(0, dtype=float)


class _InnerSolver:
    resource_request = ResourceRequest(threads=2, gpus=0, backend="local")

    def run(self, return_dict: bool = False):
        _ = return_dict
        return {"objective": np.array([0.0], dtype=float), "violation": 0.0, "status": "ok"}


def _build_solver(name: str, threads: int, with_inner: bool):
    solver = EvolutionSolver(_Problem(), pop_size=4, max_generations=2)
    solver.name = name
    solver.resource_request = ResourceRequest(threads=threads, gpus=0, backend="local", label=name)
    if with_inner:
        solver.problem.inner_runtime_evaluator = InnerRuntimeEvaluator(
            solver_factory=lambda outer, req: _InnerSolver(),
            parent_contract="outer.default",
        )
    return solver


def demo_single():
    regimes = [RegimeSpec(name="solver_a", build_solver=lambda: _build_solver("solver_a", 2, False))]
    mgr = SolverManager(regimes=regimes, offer=ResourceOffer(threads=4, gpus=0, backend="local"))
    print(mgr.run(return_dict=True))


def demo_over_budget():
    regimes = [
        RegimeSpec(name="solver_a", build_solver=lambda: _build_solver("solver_a", 4, True)),
        RegimeSpec(name="solver_b", build_solver=lambda: _build_solver("solver_b", 4, True)),
    ]
    mgr = SolverManager(regimes=regimes, offer=ResourceOffer(threads=8, gpus=0, backend="local"))
    try:
        mgr.run(return_dict=True)
    except Exception as exc:
        print(f"[expected] over budget: {exc}")


if __name__ == "__main__":
    demo_single()
    demo_over_budget()
