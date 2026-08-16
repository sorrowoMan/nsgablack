"""Canonical pipeline entry for the NSGA-II basic Case."""

from __future__ import annotations

from typing import Any, Mapping

from .config import PipelineRegistry, build_pipeline as _build_registered_pipeline
from .config import get_pipeline_registry


def build_pipeline(
    registry: PipelineRegistry | None = None,
    key: str = "default",
    *,
    resource_context: Mapping[str, Any] | None = None,
    component_overrides: Mapping[str, Any] | None = None,
):
    """Resolve the declared pipeline through the Case registry."""

    del resource_context
    overrides = dict(component_overrides or {})
    selected_registry = registry or get_pipeline_registry()
    selected_key = str(overrides.get("pipeline_key", key))
    return _build_registered_pipeline(selected_registry, selected_key)


__all__ = ["build_pipeline"]
