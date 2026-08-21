# -*- coding: utf-8 -*-
"""Project-level orchestration config for the gmm_em_vs_de example."""

from __future__ import annotations

PROJECT_NAME = "gmm_em_vs_de"

L0 = {
    "namespace": "examples.cases.gmm_em_vs_de",
    "offer": {"threads": 4, "gpus": 0, "backend": "local"},
    "policy": {"mode": "auto", "cpu_oversubscribe": True},
    "default_request": {"threads": 1, "gpus": 0, "backend": "local"},
    "compute_backend": "auto",
    "execution_backend": "local",
}

STAGES = [
    {
        "name": "main",
        "cases": ["gmm_em_vs_de"],
        "resource_requests": {"gmm_em_vs_de": {"threads": 1, "gpus": 0, "backend": "local"}},
        "component_overrides": {
            "gmm_em_vs_de": {
                "config": {
                    "k": 3,
                    "n_samples": 120,
                    "n_features": 2,
                    "pop_size": 8,
                    "max_steps": 3,
                    "random_seed": 42,
                }
            }
        },
    },
]

GROUPS = {
    "default": {"stages": ["main"]},
}
