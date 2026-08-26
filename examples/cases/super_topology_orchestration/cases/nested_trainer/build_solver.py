"""Canonical nested Trainer assembly entry."""

from __future__ import annotations

from .adapter import NestedFitMethod
from .pipeline import NestedModelCodec
from .problem import NestedLearningProblem
from .solver import NestedTrainerCase


def build_solver(config=None, *, resource_context=None, component_overrides=None):
    del config
    overrides = dict(component_overrides or {})
    candidate = overrides.get("outer_candidate", [0.5, 0.5])
    return NestedTrainerCase(
        NestedLearningProblem(candidate),
        NestedModelCodec(),
        NestedFitMethod(),
        resource_context=resource_context,
        component_overrides=overrides,
    )
