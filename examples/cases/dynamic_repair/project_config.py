# -*- coding: utf-8 -*-
"""Project-level orchestration config for the dynamic_repair example."""

from __future__ import annotations

PROJECT_NAME = "dynamic_repair"

L0 = {
    "namespace": "examples.cases.dynamic_repair",
    "offer": {"threads": 4, "gpus": 0, "backend": "local"},
    "policy": {"mode": "auto", "cpu_oversubscribe": True},
    "default_request": {"threads": 1, "gpus": 0, "backend": "local"},
    "compute_backend": "auto",
    "execution_backend": "local",
}

STAGES = [
    {
        "name": "main",
        "cases": ["dynamic_repair"],
        "resource_requests": {"dynamic_repair": {"threads": 1, "gpus": 0, "backend": "local"}},
    },
]

GROUPS = {
    "default": {"stages": ["main"]},
}
