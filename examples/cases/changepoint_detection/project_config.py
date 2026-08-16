# -*- coding: utf-8 -*-
"""Project-level orchestration config for the changepoint_detection example."""

from __future__ import annotations

PROJECT_NAME = "changepoint_detection"

L0 = {
    "namespace": "examples.cases.changepoint_detection",
    "offer": {"threads": 4, "gpus": 0, "backend": "local"},
    "policy": {"mode": "auto", "cpu_oversubscribe": True},
    "default_request": {"threads": 1, "gpus": 0, "backend": "local"},
    "compute_backend": "auto",
    "execution_backend": "local",
}

STAGES = [
    {
        "name": "main",
        "cases": ["changepoint_detection"],
        "resource_requests": {"changepoint_detection": {"threads": 1, "gpus": 0, "backend": "local"}},
        "mode": "cli",
    },
]

GROUPS = {
    "default": {"stages": ["main"]},
}
