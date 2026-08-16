# -*- coding: utf-8 -*-
"""Project-level orchestration config for the wrapper_fs example."""

from __future__ import annotations

PROJECT_NAME = "wrapper_fs"

L0 = {
    "namespace": "examples.cases.wrapper_fs",
    "offer": {"threads": 4, "gpus": 0, "backend": "local"},
    "policy": {"mode": "auto", "cpu_oversubscribe": True},
    "default_request": {"threads": 1, "gpus": 0, "backend": "local"},
    "compute_backend": "auto",
    "execution_backend": "local",
}

STAGES = [
    {
        "name": "main",
        "cases": ["wrapper_fs"],
        "resource_requests": {"wrapper_fs": {"threads": 1, "gpus": 0, "backend": "local"}},
        "mode": "cli",
    },
]

GROUPS = {
    "default": {"stages": ["main"]},
}
