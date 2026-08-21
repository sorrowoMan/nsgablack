"""Normalize the transport-safe ETF evaluation payload."""

from __future__ import annotations

from typing import Any, Mapping


def build_pipeline(
    *,
    config: Mapping[str, Any] | None = None,
    component_overrides: Mapping[str, Any] | None = None,
) -> dict[str, dict[str, Any]]:
    overrides = dict(component_overrides or {})
    case_config = dict(config or {})
    case_config.update(dict(overrides.pop("config", {}) or {}))
    walkforward = dict(overrides.pop("walkforward", {}) or {})
    lane_bundle = dict(overrides.pop("lane_bundle", {}) or {})
    if overrides:
        raise ValueError(
            "unsupported ETF lane evaluation overrides: "
            + str(sorted(overrides))
        )
    return {
        "config": case_config,
        "walkforward": walkforward,
        "lane_bundle": lane_bundle,
    }


__all__ = ["build_pipeline"]
