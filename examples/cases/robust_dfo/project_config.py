# -*- coding: utf-8 -*-
"""Project-level orchestration config for the robust_dfo example."""

from __future__ import annotations

PROJECT_NAME = "robust_dfo"

L0 = {
    "namespace": "examples.cases.robust_dfo",
    "offer": {"threads": 4, "gpus": 0, "backend": "local"},
    "policy": {"mode": "auto", "cpu_oversubscribe": True},
    "default_request": {"threads": 1, "gpus": 0, "backend": "local"},
    "compute_backend": "auto",
    "execution_backend": "local",
}

STAGES = [
    {
        "name": "main",
        "cases": ["robust_dfo"],
        "resource_requests": {"robust_dfo": {"threads": 1, "gpus": 0, "backend": "local"}},
    },
]

GROUPS = {
    "default": {"stages": ["main"]},
}
