"""Canonical solver case assembly entry."""

from .pipeline import build_pipeline
from .problem import build_problem
from .adapter.refinement import build_refinement_adapter
from nsgablack.project.starter import build_starter_solver
from nsgablack.core import PoolRetentionPolicy


def build_solver(config=None, *, resource_context=None, component_overrides=None):
    """Assemble and return one solver case."""

    pipeline = build_pipeline(
        resource_context=resource_context,
        component_overrides=component_overrides,
    )
    options = dict(config or {})
    overrides = {"adapter": build_refinement_adapter(), **dict(component_overrides or {})}
    solver = build_starter_solver(
        problem=build_problem(), pipeline=pipeline,
        max_steps=int(options.get("max_steps", 25)),
        resource_context=resource_context, component_overrides=overrides,
    )
    solver.set_solution_pool_retention(PoolRetentionPolicy(
        idle_steps=int(options.get("pool_idle_steps", 2)),
    ))
    return solver
