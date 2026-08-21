from __future__ import annotations

from typing import Any, Mapping

from evaluation.trainer import EtfLaneEvaluationCase
from pipeline.main import build_pipeline


def build_solver(
    config=None,
    *,
    resource_context: Mapping[str, Any] | None = None,
    component_overrides: Mapping[str, Any] | None = None,
):
    payload = build_pipeline(config=config, component_overrides=component_overrides)
    return EtfLaneEvaluationCase(
        config=payload["config"],
        walkforward=payload["walkforward"],
        lane_bundle=payload["lane_bundle"],
        resource_context=resource_context,
    )


__all__ = ["build_solver"]
