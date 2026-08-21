# -*- coding: utf-8 -*-
"""Project-level orchestration config for the ransac example."""

from __future__ import annotations

PROJECT_NAME = "ransac"

L0 = {
    "namespace": "examples.cases.ransac",
    "offer": {"threads": 4, "gpus": 0, "backend": "local"},
    "policy": {"mode": "auto", "cpu_oversubscribe": True},
    "default_request": {"threads": 1, "gpus": 0, "backend": "local"},
    "compute_backend": "auto",
    "execution_backend": "local",
}

STAGES = [
    {
        "name": "main",
        "cases": ["ransac"],
        "resource_requests": {"ransac": {"threads": 1, "gpus": 0, "backend": "local"}},
        "component_overrides": {
            "ransac": {"config": {"pop_size": 8, "max_steps": 3}}
        },
    },
]

GROUPS = {
    "default": {"stages": ["main"]},
}
