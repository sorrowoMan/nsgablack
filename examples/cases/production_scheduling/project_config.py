# -*- coding: utf-8 -*-
"""Project-level orchestration config for the production_scheduling example."""

from __future__ import annotations

PROJECT_NAME = "production_scheduling"

L0 = {
    "namespace": "examples.cases.production_scheduling",
    "offer": {"threads": 4, "gpus": 0, "backend": "local"},
    "policy": {"mode": "auto", "cpu_oversubscribe": True},
    "default_request": {"threads": 1, "gpus": 0, "backend": "local"},
    "compute_backend": "auto",
    "execution_backend": "local",
}

STAGES = [
    {
        "name": "main",
        "cases": ["production_scheduling"],
        "resource_requests": {"production_scheduling": {"threads": 1, "gpus": 0, "backend": "local"}},
        "mode": "cli",
    },
]

GROUPS = {
    "default": {"stages": ["main"]},
}
