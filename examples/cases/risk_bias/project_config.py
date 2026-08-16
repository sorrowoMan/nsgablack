# -*- coding: utf-8 -*-
"""Project-level orchestration config for the risk_bias example."""

from __future__ import annotations

PROJECT_NAME = "risk_bias"

L0 = {
    "namespace": "examples.cases.risk_bias",
    "offer": {"threads": 4, "gpus": 0, "backend": "local"},
    "policy": {"mode": "auto", "cpu_oversubscribe": True},
    "default_request": {"threads": 1, "gpus": 0, "backend": "local"},
    "compute_backend": "auto",
    "execution_backend": "local",
}

STAGES = [
    {
        "name": "main",
        "cases": ["risk_bias"],
        "resource_requests": {"risk_bias": {"threads": 1, "gpus": 0, "backend": "local"}},
    },
]

GROUPS = {
    "default": {"stages": ["main"]},
}
