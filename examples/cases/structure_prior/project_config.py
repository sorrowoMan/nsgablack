# -*- coding: utf-8 -*-
"""Project-level orchestration config for the structure_prior example."""

from __future__ import annotations

PROJECT_NAME = "structure_prior"

L0 = {
    "namespace": "examples.cases.structure_prior",
    "offer": {"threads": 4, "gpus": 0, "backend": "local"},
    "policy": {"mode": "auto", "cpu_oversubscribe": True},
    "default_request": {"threads": 1, "gpus": 0, "backend": "local"},
    "compute_backend": "auto",
    "execution_backend": "local",
}

STAGES = [
    {
        "name": "main",
        "cases": ["structure_prior"],
        "resource_requests": {"structure_prior": {"threads": 1, "gpus": 0, "backend": "local"}},
    },
]

GROUPS = {
    "default": {"stages": ["main"]},
}
