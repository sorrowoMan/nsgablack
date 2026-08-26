"""Canonical baseline Solver assembly entry."""

from __future__ import annotations

from nsgablack.core import ComposableSolver

from .adapter import build_adapter
from .pipeline import build_pipeline
from .problem import BaselineOptimizationProblem
from .solver import BaselineSolverCase


def build_solver(config=None, *, resource_context=None, component_overrides=None):
    del config
    solver = ComposableSolver(
        BaselineOptimizationProblem(),
        adapter=build_adapter(),
        representation_pipeline=build_pipeline(),
        resource_context=resource_context,
    )
    return BaselineSolverCase(solver, component_overrides=component_overrides)
