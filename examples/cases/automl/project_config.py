# -*- coding: utf-8 -*-
"""Project-level orchestration config for the automl example."""

from __future__ import annotations

PROJECT_NAME = "automl"

L0 = {
    "namespace": "examples.cases.automl",
    "offer": {"threads": 4, "gpus": 0, "backend": "local"},
    "policy": {"mode": "auto", "cpu_oversubscribe": True},
    "default_request": {"threads": 1, "gpus": 0, "backend": "local"},
    "compute_backend": "auto",
    "execution_backend": "local",
}

STAGES = [
    {
        "name": "main",
        "cases": ["automl"],
        "resource_requests": {"automl": {"threads": 1, "gpus": 0, "backend": "local"}},
        "component_overrides": {
            "automl": {
                "config": {
                    "n_samples": 120,
                    "n_features": 6,
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
