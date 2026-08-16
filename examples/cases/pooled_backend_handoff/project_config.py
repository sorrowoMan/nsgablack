# -*- coding: utf-8 -*-
"""Project-level orchestration config for the pooled_backend_handoff example."""

from __future__ import annotations

PROJECT_NAME = "pooled_backend_handoff"

L0 = {
    "namespace": "examples.cases.pooled_backend_handoff",
    "offer": {"threads": 4, "gpus": 0, "backend": "local"},
    "policy": {"mode": "auto", "cpu_oversubscribe": True},
    "default_request": {"threads": 1, "gpus": 0, "backend": "local"},
    "compute_backend": "auto",
    "execution_backend": "local",
}

STAGES = [
    {
        "name": "main",
        "cases": ["pooled_backend_handoff"],
        "resource_requests": {"pooled_backend_handoff": {"threads": 1, "gpus": 0, "backend": "local"}},
    },
]

GROUPS = {
    "default": {"stages": ["main"]},
}
