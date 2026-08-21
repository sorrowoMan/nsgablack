# -*- coding: utf-8 -*-
"""Project-level orchestration config for the production_scheduling example."""

from __future__ import annotations

PROJECT_NAME = "production_scheduling"

L0 = {
    "namespace": "examples.cases.production_scheduling",
    "offer": {"threads": 4, "gpus": 0, "backend": "local"},
    "policy": {"mode": "auto", "cpu_oversubscribe": True},
    "default_request": {"threads": 1, "gpus": 0, "backend": "local"},
    "compute_backend": "auto",
    "execution_backend": "local",
}

STAGES = [
    {
        "name": "main",
        "cases": ["production_scheduling"],
        "resource_requests": {"production_scheduling": {"threads": 1, "gpus": 0, "backend": "local"}},
        # The formal Project entry is an executable smoke profile.  The
        # realistic 36-generation profiles remain available under the Case's
        # config/ directory and through explicit CLI arguments.
        "component_overrides": {
            "production_scheduling": {
                "argv": [
                    "--machines", "4",
                    "--materials", "10",
                    "--pop-size", "8",
                    "--generations", "1",
                    "--moead-pop-size", "8",
                    "--moead-neighborhood", "4",
                    "--vns-batch-size", "4",
                    "--parallel-backend", "thread",
                    "--parallel-workers", "1",
                    "--no-export",
                    "--no-run-logs",
                    "--seed", "1",
                ]
            }
        },
    },
]

GROUPS = {
    "default": {"stages": ["main"]},
}
