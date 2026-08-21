# -*- coding: utf-8 -*-
"""Project-level orchestration config for the anomaly_detection example."""

from __future__ import annotations

PROJECT_NAME = "anomaly_detection"

L0 = {
    "namespace": "examples.cases.anomaly_detection",
    "offer": {"threads": 4, "gpus": 0, "backend": "local"},
    "policy": {"mode": "auto", "cpu_oversubscribe": True},
    "default_request": {"threads": 1, "gpus": 0, "backend": "local"},
    "compute_backend": "auto",
    "execution_backend": "local",
}

STAGES = [
    {
        "name": "main",
        "cases": ["anomaly_detection"],
        "resource_requests": {"anomaly_detection": {"threads": 1, "gpus": 0, "backend": "local"}},
        "component_overrides": {
            "anomaly_detection": {
                "config": {
                    "mode": "lof",
                    "pop_size": 8,
                    "max_steps": 3,
                    "n_samples": 160,
                    "n_outliers": 16,
                    "n_features": 4,
                    "seed": 42,
                }
            }
        },
    },
]

GROUPS = {
    "default": {"stages": ["main"]},
}
