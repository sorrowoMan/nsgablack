# -*- coding: utf-8 -*-
"""Project-level orchestration config for the tr_subspace_frontier example."""

from __future__ import annotations

PROJECT_NAME = "tr_subspace_frontier"

L0 = {
    "namespace": "examples.cases.tr_subspace_frontier",
    "offer": {"threads": 4, "gpus": 0, "backend": "local"},
    "policy": {"mode": "auto", "cpu_oversubscribe": True},
    "default_request": {"threads": 1, "gpus": 0, "backend": "local"},
    "compute_backend": "auto",
    "execution_backend": "local",
}

STAGES = [
    {
        "name": "main",
        "cases": ["tr_subspace_frontier"],
        "resource_requests": {"tr_subspace_frontier": {"threads": 1, "gpus": 0, "backend": "local"}},
    },
]

GROUPS = {
    "default": {"stages": ["main"]},
}
