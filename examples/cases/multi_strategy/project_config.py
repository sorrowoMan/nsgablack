# -*- coding: utf-8 -*-
"""Project-level orchestration config for the multi_strategy example."""

from __future__ import annotations

PROJECT_NAME = "multi_strategy"

L0 = {
    "namespace": "examples.cases.multi_strategy",
    "offer": {"threads": 4, "gpus": 0, "backend": "local"},
    "policy": {"mode": "auto", "cpu_oversubscribe": True},
    "default_request": {"threads": 1, "gpus": 0, "backend": "local"},
    "compute_backend": "auto",
    "execution_backend": "local",
}

STAGES = [
    {
        "name": "main",
        "cases": ["multi_strategy"],
        "resource_requests": {"multi_strategy": {"threads": 1, "gpus": 0, "backend": "local"}},
    },
]

GROUPS = {
    "default": {"stages": ["main"]},
}
