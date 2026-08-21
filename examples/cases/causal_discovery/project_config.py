# -*- coding: utf-8 -*-
"""Project-level orchestration config for the causal_discovery example."""

from __future__ import annotations

PROJECT_NAME = "causal_discovery"

L0 = {
    "namespace": "examples.cases.causal_discovery",
    "offer": {"threads": 4, "gpus": 0, "backend": "local"},
    "policy": {"mode": "auto", "cpu_oversubscribe": True},
    "default_request": {"threads": 1, "gpus": 0, "backend": "local"},
    "compute_backend": "auto",
    "execution_backend": "local",
}

STAGES = [
    {
        "name": "main",
        "cases": ["causal_discovery"],
        "resource_requests": {"causal_discovery": {"threads": 1, "gpus": 0, "backend": "local"}},
        "component_overrides": {
            "causal_discovery": {
                "config": {
                    "mode": "pc",
                    "n_vars": 4,
                    "pop_size": 6,
                    "max_steps": 2,
                    "random_seed": 42,
                }
            }
        },
    },
]

GROUPS = {
    "default": {"stages": ["main"]},
}
