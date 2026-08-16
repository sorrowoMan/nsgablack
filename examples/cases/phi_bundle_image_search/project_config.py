# -*- coding: utf-8 -*-
"""Project-level orchestration config for the phi_bundle_image_search example."""

from __future__ import annotations

PROJECT_NAME = "phi_bundle_image_search"

L0 = {
    "namespace": "examples.cases.phi_bundle_image_search",
    "offer": {"threads": 4, "gpus": 0, "backend": "local"},
    "policy": {"mode": "auto", "cpu_oversubscribe": True},
    "default_request": {"threads": 1, "gpus": 0, "backend": "local"},
    "compute_backend": "auto",
    "execution_backend": "local",
}

STAGES = [
    {
        "name": "main",
        "cases": ["phi_bundle_image_search"],
        "resource_requests": {"phi_bundle_image_search": {"threads": 1, "gpus": 0, "backend": "local"}},
    },
]

GROUPS = {
    "default": {"stages": ["main"]},
}
