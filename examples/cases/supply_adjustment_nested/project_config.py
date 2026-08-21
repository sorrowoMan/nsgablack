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
        "component_overrides": {
            "supply_adjustment_nested": {
                "argv": [
                    "--machines", "4",
                    "--materials", "10",
                    "--days", "7",
                    "--pop-size", "4",
                    "--generations", "1",
                    "--inner-eval-mode", "fast",
                    "--inner-trials", "1",
                    "--inner-max-calls", "16",
                    "--no-decision-trace",
                    "--no-profiler",
                    "--seed", "1",
                ]
            }
        },
    },
]

GROUPS = {
    "default": {"stages": ["main"]},
}
