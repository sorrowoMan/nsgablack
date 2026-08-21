# -*- coding: utf-8 -*-
"""Project-level orchestration config for the graph_coloring example."""

from __future__ import annotations

PROJECT_NAME = "graph_coloring"

L0 = {
    "namespace": "examples.cases.graph_coloring",
    "offer": {"threads": 4, "gpus": 0, "backend": "local"},
    "policy": {"mode": "auto", "cpu_oversubscribe": True},
    "default_request": {"threads": 1, "gpus": 0, "backend": "local"},
    "compute_backend": "auto",
    "execution_backend": "local",
}

STAGES = [
    {
        "name": "main",
        "cases": ["graph_coloring"],
        "resource_requests": {"graph_coloring": {"threads": 1, "gpus": 0, "backend": "local"}},
        "component_overrides": {
            "graph_coloring": {
                "config": {"max_colors": 6, "pop_size": 8, "max_steps": 3}
            }
        },
    },
]

GROUPS = {
    "default": {"stages": ["main"]},
}
