"""Canonical solver case assembly entry."""

from .pipeline import build_pipeline
from .problem import build_problem
from .adapter.pool_example import build_pool_adapter
from nsgablack.project.starter import build_starter_solver


def build_solver(config=None, *, resource_context=None, component_overrides=None):
    """Assemble and return one solver case."""

    pipeline = build_pipeline(
        resource_context=resource_context,
        component_overrides=component_overrides,
    )
    options = dict(config or {})
    overrides = {"adapter": build_pool_adapter(
        int(options.get("population_size", 4)), stagnation_steps=1, recovery_steps=2),
        **dict(component_overrides or {})}
    return build_starter_solver(
        problem=build_problem(), pipeline=pipeline,
        max_steps=int(options.get("max_steps", 7)),
        resource_context=resource_context, component_overrides=overrides,
    )
