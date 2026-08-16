# -*- coding: utf-8 -*-
"""Project-level orchestration config for the classification_threshold_calibration example."""

from __future__ import annotations

PROJECT_NAME = "classification_threshold_calibration"

L0 = {
    "namespace": "examples.cases.classification_threshold_calibration",
    "offer": {"threads": 4, "gpus": 0, "backend": "local"},
    "policy": {"mode": "auto", "cpu_oversubscribe": True},
    "default_request": {"threads": 1, "gpus": 0, "backend": "local"},
    "compute_backend": "auto",
    "execution_backend": "local",
}

STAGES = [
    {
        "name": "main",
        "cases": ["classification_threshold_calibration"],
        "resource_requests": {"classification_threshold_calibration": {"threads": 1, "gpus": 0, "backend": "local"}},
    },
]

GROUPS = {
    "default": {"stages": ["main"]},
}
