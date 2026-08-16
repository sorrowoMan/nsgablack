# -*- coding: utf-8 -*-
"""Project-level orchestration config for the l0_distributed_worker example."""

from __future__ import annotations

PROJECT_NAME = "l0_distributed_worker"

L0 = {
    "namespace": "examples.cases.l0_distributed_worker",
    "offer": {"threads": 4, "gpus": 0, "backend": "local"},
    "policy": {"mode": "auto", "cpu_oversubscribe": True},
    "default_request": {"threads": 1, "gpus": 0, "backend": "local"},
    "compute_backend": "auto",
    "execution_backend": "local",
}

STAGES = [
    {
        "name": "main",
        "cases": ["l0_distributed_worker"],
        "resource_requests": {"l0_distributed_worker": {"threads": 1, "gpus": 0, "backend": "local"}},
    },
]

GROUPS = {
    "default": {"stages": ["main"]},
}
