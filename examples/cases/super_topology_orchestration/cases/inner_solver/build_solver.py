"""Canonical inner Solver assembly entry."""

from __future__ import annotations

from nsgablack.core import ComposableSolver

from .adapter import build_adapter
from .pipeline import build_pipeline
from .problem import CalibrationProblem
from .solver import InnerSolverCase


def build_solver(config=None, *, resource_context=None, component_overrides=None):
    del config
    overrides = dict(component_overrides or {})
    target = float(overrides.get("target", 0.0))
    solver = ComposableSolver(
        CalibrationProblem(target),
        adapter=build_adapter(),
        representation_pipeline=build_pipeline(),
        resource_context=resource_context,
    )
    return InnerSolverCase(solver, component_overrides=overrides)
