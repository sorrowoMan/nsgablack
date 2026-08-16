"""Canonical outer-search pipeline for the nested mlblack Case."""

from __future__ import annotations

from typing import Any, Mapping

import numpy as np

from nsgablack.representation import RepresentationPipeline
from nsgablack.representation.continuous import ClipRepair, ContextGaussianMutation, UniformInitializer


def build_pipeline(
    problem,
    *,
    mutation_sigma: float,
    resource_context: Mapping[str, Any] | None = None,
    component_overrides: Mapping[str, Any] | None = None,
) -> RepresentationPipeline:
    """Build the bounded outer-search representation pipeline."""

    del resource_context
    overrides = dict(component_overrides or {})
    if overrides.get("representation_pipeline") is not None:
        return overrides["representation_pipeline"]
    lows = np.array([problem.bounds[f"x{i}"][0] for i in range(problem.dimension)], dtype=float)
    highs = np.array([problem.bounds[f"x{i}"][1] for i in range(problem.dimension)], dtype=float)
    return RepresentationPipeline(
        initializer=UniformInitializer(low=lows, high=highs),
        mutator=ContextGaussianMutation(
            base_sigma=float(mutation_sigma),
            sigma_key="mutation_sigma",
            low=lows,
            high=highs,
        ),
        repair=ClipRepair(low=lows, high=highs),
    )


__all__ = ["build_pipeline"]
