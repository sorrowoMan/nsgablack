"""Canonical representation-pipeline entry for clustering."""

from __future__ import annotations

from typing import Any, Mapping

from nsgablack.representation import RepresentationPipeline
from nsgablack.representation.continuous import ClipRepair, ContextGaussianMutation, UniformInitializer


def build_pipeline(
    problem,
    *,
    resource_context: Mapping[str, Any] | None = None,
    component_overrides: Mapping[str, Any] | None = None,
) -> RepresentationPipeline:
    """Build the bounded centroid-vector pipeline."""

    del resource_context
    overrides = dict(component_overrides or {})
    if overrides.get("representation_pipeline") is not None:
        return overrides["representation_pipeline"]
    low = [bound[0] for bound in problem.bounds]
    high = [bound[1] for bound in problem.bounds]
    return RepresentationPipeline(
        initializer=UniformInitializer(low=low, high=high),
        mutator=ContextGaussianMutation(
            base_sigma=0.15,
            sigma_key="mutation_sigma",
            low=low,
            high=high,
        ),
        repair=ClipRepair(low=low, high=high),
    )


__all__ = ["build_pipeline"]
