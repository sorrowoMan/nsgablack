"""Canonical baseline Trainer assembly entry."""

from __future__ import annotations

from .adapter import ClosedFormFitMethod
from .pipeline import ClosedFormDataPipeline
from .problem import ClosedFormRegressionProblem
from .solver import BaselineTrainerCase


def build_solver(config=None, *, resource_context=None, component_overrides=None):
    del config
    return BaselineTrainerCase(
        ClosedFormRegressionProblem(),
        ClosedFormDataPipeline(),
        ClosedFormFitMethod(),
        resource_context=resource_context,
        component_overrides=component_overrides,
    )
