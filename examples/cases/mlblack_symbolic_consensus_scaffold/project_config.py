# -*- coding: utf-8 -*-
"""Project-level orchestration config for the mlblack_symbolic_consensus_scaffold example."""

from __future__ import annotations

PROJECT_NAME = "mlblack_symbolic_consensus_scaffold"

L0 = {
    "namespace": "examples.cases.mlblack_symbolic_consensus_scaffold",
    "offer": {"threads": 4, "gpus": 0, "backend": "local"},
    "policy": {"mode": "auto", "cpu_oversubscribe": True},
    "default_request": {"threads": 1, "gpus": 0, "backend": "local"},
    "compute_backend": "auto",
    "execution_backend": "local",
}

STAGES = [
    {
        "name": "main",
        "cases": ["mlblack_symbolic_consensus_scaffold"],
        "resource_requests": {"mlblack_symbolic_consensus_scaffold": {"threads": 1, "gpus": 0, "backend": "local"}},
        "mode": "cli",
    },
]

GROUPS = {
    "default": {"stages": ["main"]},
}
