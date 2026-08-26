"""Canonical outer Solver assembly entry."""

from __future__ import annotations

from nsgablack.core import ComposableSolver

from .adapter import build_topology_adapter
from .pipeline import build_pipeline
from .problem import NestedTrainingOptimizationProblem
from .solver import OuterSearchCase


def build_solver(config=None, *, resource_context=None, component_overrides=None):
    del config
    problem = NestedTrainingOptimizationProblem()
    solver = ComposableSolver(
        problem,
        adapter=build_topology_adapter(),
        representation_pipeline=build_pipeline(),
        resource_context=resource_context,
    )
    return OuterSearchCase(solver, component_overrides=component_overrides)
