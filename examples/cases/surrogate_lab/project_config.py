# -*- coding: utf-8 -*-
"""Project-level orchestration config for the surrogate_lab example."""

from __future__ import annotations

PROJECT_NAME = "surrogate_lab"

L0 = {
    "namespace": "examples.cases.surrogate_lab",
    "offer": {"threads": 4, "gpus": 0, "backend": "local"},
    "policy": {"mode": "auto", "cpu_oversubscribe": True},
    "default_request": {"threads": 1, "gpus": 0, "backend": "local"},
    "compute_backend": "auto",
    "execution_backend": "local",
}

STAGES = [
    {
        "name": "main",
        "cases": ["surrogate_lab"],
        "resource_requests": {"surrogate_lab": {"threads": 1, "gpus": 0, "backend": "local"}},
    },
]

GROUPS = {
    "default": {"stages": ["main"]},
}
