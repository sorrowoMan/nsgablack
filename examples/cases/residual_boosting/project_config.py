# -*- coding: utf-8 -*-
"""Project-level orchestration config for the residual_boosting example."""

from __future__ import annotations

PROJECT_NAME = "residual_boosting"

L0 = {
    "namespace": "examples.cases.residual_boosting",
    "offer": {"threads": 4, "gpus": 0, "backend": "local"},
    "policy": {"mode": "auto", "cpu_oversubscribe": True},
    "default_request": {"threads": 1, "gpus": 0, "backend": "local"},
    "compute_backend": "auto",
    "execution_backend": "local",
}

STAGES = [
    {
        "name": "main",
        "cases": ["residual_boosting"],
        "resource_requests": {"residual_boosting": {"threads": 1, "gpus": 0, "backend": "local"}},
    },
]

GROUPS = {
    "default": {"stages": ["main"]},
}
