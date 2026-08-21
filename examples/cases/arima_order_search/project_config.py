# -*- coding: utf-8 -*-
"""Project-level orchestration config for the arima_order_search example."""

from __future__ import annotations

PROJECT_NAME = "arima_order_search"

L0 = {
    "namespace": "examples.cases.arima_order_search",
    "offer": {"threads": 4, "gpus": 0, "backend": "local"},
    "policy": {"mode": "auto", "cpu_oversubscribe": True},
    "default_request": {"threads": 1, "gpus": 0, "backend": "local"},
    "compute_backend": "auto",
    "execution_backend": "local",
}

STAGES = [
    {
        "name": "main",
        "cases": ["arima_order_search"],
        "resource_requests": {"arima_order_search": {"threads": 1, "gpus": 0, "backend": "local"}},
        "component_overrides": {
            "arima_order_search": {
                "config": {
                    "pop_size": 4,
                    "max_steps": 1,
                    "series_length": 80,
                    "max_p": 2,
                    "max_d": 1,
                    "max_q": 2,
                    "seed": 42,
                }
            }
        },
    },
]

GROUPS = {
    "default": {"stages": ["main"]},
}
