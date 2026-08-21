# -*- coding: utf-8 -*-
"""Project-level orchestration config for the shap example."""

from __future__ import annotations

PROJECT_NAME = "shap"

L0 = {
    "namespace": "examples.cases.shap",
    "offer": {"threads": 4, "gpus": 0, "backend": "local"},
    "policy": {"mode": "auto", "cpu_oversubscribe": True},
    "default_request": {"threads": 1, "gpus": 0, "backend": "local"},
    "compute_backend": "auto",
    "execution_backend": "local",
}

STAGES = [
    {
        "name": "main",
        "cases": ["shap"],
        "resource_requests": {"shap": {"threads": 1, "gpus": 0, "backend": "local"}},
        "component_overrides": {
            "shap": {"config": {"seed": 42, "n_coalitions": 32, "max_steps": 3}}
        },
    },
]

GROUPS = {
    "default": {"stages": ["main"]},
}
