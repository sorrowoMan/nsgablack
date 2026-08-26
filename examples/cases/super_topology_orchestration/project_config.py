"""Project configuration for the complete cross-framework orchestration topology."""

from __future__ import annotations

PROJECT_NAME = "super_topology_orchestration"

L0 = {
    "namespace": "examples.cases.super_topology_orchestration",
    "offer": {
        "workers": 8,
        "threads": 8,
        "gpus": 0,
        "backend": "local",
        "device_tokens": [],
    },
    "policy": {
        "mode": "strict",
        "gpu_sharing": "exclusive",
        "cpu_oversubscribe": False,
        "max_workers": 8,
        "max_threads": 8,
    },
    "default_request": {
        "workers": 1,
        "threads": 1,
        "gpus": 0,
        "backend": "local",
        "device": "cpu",
    },
    "compute_backend": "auto",
    "execution_backend": "local",
    "lease_backend": "sqlite",
    "lease_path": ".blackbase/l0_leases.sqlite",
    "lease_ttl_seconds": 30,
    "lease_heartbeat_seconds": 10,
    "control_active_ttl_seconds": 120,
    "control_heartbeat_seconds": 30,
    "control_retention_seconds": 0,
    "budgets": {"evaluations": 128},
    "artifacts": {
        "path": ".blackbase/artifacts",
        "allow_unsafe_serializers": False,
    },
    "termination": {
        "mode": "cooperative",
        "grace_seconds": 5.0,
        "kill_grace_seconds": 1.0,
        "poll_interval_seconds": 0.05,
    },
}

STAGES = [
    {
        "name": "workflow",
        "policy": "dag",
        "failure_policy": "fail_fast",
        "max_workers": 2,
        "cases": ["baseline_solver", "baseline_trainer", "outer_search"],
        "resource_requests": {
            "baseline_solver": {
                "workers": 1,
                "threads": 1,
                "gpus": 0,
                "backend": "local",
                "device": "cpu",
            },
            "baseline_trainer": {
                "workers": 1,
                "threads": 1,
                "gpus": 0,
                "backend": "local",
                "device": "cpu",
            },
            "outer_search": {
                "workers": 1,
                "threads": 4,
                "gpus": 0,
                "backend": "local",
                "device": "cpu",
            },
        },
        "input_artifacts": {
            "outer_search": {
                "solver_baseline": "baseline_solver.summary",
                "trainer_baseline": "baseline_trainer.summary",
            },
        },
    },
]

GROUPS = {"default": {"stages": ["workflow"]}}
