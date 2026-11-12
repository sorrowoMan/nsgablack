"""Canonical standard Case assembly for source publication."""
from .solver.case import ProductionSourcesCase


def build_solver(config=None, *, resource_context=None, component_overrides=None):
    if config:
        raise ValueError("production_sources accepts explicit component_overrides")
    return ProductionSourcesCase(resource_context=resource_context, **dict(component_overrides or {}))
