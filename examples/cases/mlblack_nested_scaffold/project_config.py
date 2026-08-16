# -*- coding: utf-8 -*-
"""Project-level orchestration config for the mlblack_nested_scaffold example."""

from __future__ import annotations

PROJECT_NAME = "mlblack_nested_scaffold"

L0 = {
    "namespace": "examples.cases.mlblack_nested_scaffold",
    "offer": {"threads": 4, "gpus": 0, "backend": "local"},
    "policy": {"mode": "auto", "cpu_oversubscribe": True},
    "default_request": {"threads": 1, "gpus": 0, "backend": "local"},
    "compute_backend": "auto",
    "execution_backend": "local",
}

STAGES = [
    {
        "name": "main",
        "cases": ["mlblack_nested_scaffold"],
        "resource_requests": {"mlblack_nested_scaffold": {"threads": 1, "gpus": 0, "backend": "local"}},
        "mode": "cli",
    },
]

GROUPS = {
    "default": {"stages": ["main"]},
}
