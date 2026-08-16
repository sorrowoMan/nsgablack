# -*- coding: utf-8 -*-
"""Project-level orchestration config for the trust_region_dfo example."""

from __future__ import annotations

PROJECT_NAME = "trust_region_dfo"

L0 = {
    "namespace": "examples.cases.trust_region_dfo",
    "offer": {"threads": 4, "gpus": 0, "backend": "local"},
    "policy": {"mode": "auto", "cpu_oversubscribe": True},
    "default_request": {"threads": 1, "gpus": 0, "backend": "local"},
    "compute_backend": "auto",
    "execution_backend": "local",
}

STAGES = [
    {
        "name": "main",
        "cases": ["trust_region_dfo"],
        "resource_requests": {"trust_region_dfo": {"threads": 1, "gpus": 0, "backend": "local"}},
    },
]

GROUPS = {
    "default": {"stages": ["main"]},
}
