# -*- coding: utf-8 -*-
"""Project-level orchestration config for the tsp_vrp example."""

from __future__ import annotations

PROJECT_NAME = "tsp_vrp"

L0 = {
    "namespace": "examples.cases.tsp_vrp",
    "offer": {"threads": 4, "gpus": 0, "backend": "local"},
    "policy": {"mode": "auto", "cpu_oversubscribe": True},
    "default_request": {"threads": 1, "gpus": 0, "backend": "local"},
    "compute_backend": "auto",
    "execution_backend": "local",
}

STAGES = [
    {
        "name": "main",
        "cases": ["tsp_vrp"],
        "resource_requests": {"tsp_vrp": {"threads": 1, "gpus": 0, "backend": "local"}},
        "component_overrides": {
            "tsp_vrp": {
                "config": {
                    "n_cities": 10,
                    "pop_size": 8,
                    "max_steps": 5,
                    "random_seed": 2,
                }
            }
        },
    },
]

GROUPS = {
    "default": {"stages": ["main"]},
}
