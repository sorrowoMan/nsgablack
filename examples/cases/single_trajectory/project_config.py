# -*- coding: utf-8 -*-
"""Project-level orchestration config for the single_trajectory example."""

from __future__ import annotations

PROJECT_NAME = "single_trajectory"

L0 = {
    "namespace": "examples.cases.single_trajectory",
    "offer": {"threads": 4, "gpus": 0, "backend": "local"},
    "policy": {"mode": "auto", "cpu_oversubscribe": True},
    "default_request": {"threads": 1, "gpus": 0, "backend": "local"},
    "compute_backend": "auto",
    "execution_backend": "local",
}

STAGES = [
    {
        "name": "main",
        "cases": ["single_trajectory"],
        "resource_requests": {"single_trajectory": {"threads": 1, "gpus": 0, "backend": "local"}},
    },
]

GROUPS = {
    "default": {"stages": ["main"]},
}
