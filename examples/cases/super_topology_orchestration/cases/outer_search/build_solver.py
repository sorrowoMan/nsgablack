"""Canonical outer Solver assembly entry."""

from __future__ import annotations

from nsgablack.core import ComposableSolver

from .adapter import build_topology_adapter
from .pipeline import build_pipeline
from .problem import NestedTrainingOptimizationProblem
from .plugins.working_pool import PrepareWorkingPool
from .solver import OuterSearchCase


def build_solver(config=None, *, resource_context=None, component_overrides=None):
    del config
    overrides = dict(component_overrides or {})
    problem = NestedTrainingOptimizationProblem()
    solver = ComposableSolver(
        problem,
        adapter=build_topology_adapter(),
        representation_pipeline=build_pipeline(),
        resource_context=resource_context,
    )
    working_pool = overrides.get("working_pool")
    if working_pool is not None:
        solver.adapter.set_working_pool(working_pool)
        solver.add_plugin(PrepareWorkingPool(working_pool))
    return OuterSearchCase(solver, component_overrides=overrides)
