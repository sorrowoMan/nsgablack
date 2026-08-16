# -*- coding: utf-8 -*-
"""Project-level orchestration config for the supply_adjustment_nested example."""

from __future__ import annotations

PROJECT_NAME = "supply_adjustment_nested"

L0 = {
    "namespace": "examples.cases.supply_adjustment_nested",
    "offer": {"threads": 4, "gpus": 0, "backend": "local"},
    "policy": {"mode": "auto", "cpu_oversubscribe": True},
    "default_request": {"threads": 1, "gpus": 0, "backend": "local"},
    "compute_backend": "auto",
    "execution_backend": "local",
}

STAGES = [
    {
        "name": "main",
        "cases": ["supply_adjustment_nested"],
        "resource_requests": {"supply_adjustment_nested": {"threads": 1, "gpus": 0, "backend": "local"}},
        "mode": "cli",
    },
]

GROUPS = {
    "default": {"stages": ["main"]},
}
