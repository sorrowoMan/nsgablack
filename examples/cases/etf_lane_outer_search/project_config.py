# -*- coding: utf-8 -*-
"""Project-level orchestration config for the etf_lane_outer_search example."""

from __future__ import annotations

PROJECT_NAME = "etf_lane_outer_search"

L0 = {
    "namespace": "examples.cases.etf_lane_outer_search",
    "offer": {"threads": 4, "gpus": 0, "backend": "local"},
    "policy": {"mode": "auto", "cpu_oversubscribe": True},
    "default_request": {"threads": 1, "gpus": 0, "backend": "local"},
    "compute_backend": "auto",
    "execution_backend": "local",
}

STAGES = [
    {
        "name": "main",
        "cases": ["etf_lane_outer_search"],
        "resource_requests": {"etf_lane_outer_search": {"threads": 1, "gpus": 0, "backend": "local"}},
    },
]

GROUPS = {
    "default": {"stages": ["main"]},
}
