# -*- coding: utf-8 -*-
"""Project-level orchestration config for the nsga2_basic example."""

from __future__ import annotations

PROJECT_NAME = "nsga2_basic"

L0 = {
    "namespace": "examples.cases.nsga2_basic",
    "offer": {"threads": 4, "gpus": 0, "backend": "local"},
    "policy": {"mode": "auto", "cpu_oversubscribe": True},
    "default_request": {"threads": 1, "gpus": 0, "backend": "local"},
    "compute_backend": "auto",
    "execution_backend": "local",
}

STAGES = [
    {
        "name": "main",
        "cases": ["nsga2_basic"],
        "resource_requests": {"nsga2_basic": {"threads": 1, "gpus": 0, "backend": "local"}},
    },
]

GROUPS = {
    "default": {"stages": ["main"]},
}
