# -*- coding: utf-8 -*-
"""Project-level orchestration config for the bias_gallery example."""

from __future__ import annotations

PROJECT_NAME = "bias_gallery"

L0 = {
    "namespace": "examples.cases.bias_gallery",
    "offer": {"threads": 4, "gpus": 0, "backend": "local"},
    "policy": {"mode": "auto", "cpu_oversubscribe": True},
    "default_request": {"threads": 1, "gpus": 0, "backend": "local"},
    "compute_backend": "auto",
    "execution_backend": "local",
}

STAGES = [
    {
        "name": "main",
        "cases": ["bias_gallery"],
        "resource_requests": {"bias_gallery": {"threads": 1, "gpus": 0, "backend": "local"}},
    },
]

GROUPS = {
    "default": {"stages": ["main"]},
}
