# -*- coding: utf-8 -*-
"""Project-level orchestration config for the surrogate_ea example."""

from __future__ import annotations

PROJECT_NAME = "surrogate_ea"

L0 = {
    "namespace": "examples.cases.surrogate_ea",
    "offer": {"threads": 4, "gpus": 0, "backend": "local"},
    "policy": {"mode": "auto", "cpu_oversubscribe": True},
    "default_request": {"threads": 1, "gpus": 0, "backend": "local"},
    "compute_backend": "auto",
    "execution_backend": "local",
}

STAGES = [
    {
        "name": "main",
        "cases": ["surrogate_ea"],
        "resource_requests": {"surrogate_ea": {"threads": 1, "gpus": 0, "backend": "local"}},
    },
]

GROUPS = {
    "default": {"stages": ["main"]},
}
