"""有界原生产 Case 诊断；只配置正式 Project/L0，不实现运行循环。"""

from pathlib import Path
import os
import re


PROJECT_NAME = "runtime_cost_probe"
_PROJECT_ROOT = Path(__file__).resolve().parent
RUN_ID = os.environ.get("NSGABLACK_RUNTIME_COST_RUN_ID", "manual")
if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,63}", RUN_ID):
    raise ValueError("NSGABLACK_RUNTIME_COST_RUN_ID must be one safe identifier")
_EXPECTED_RUN_ROOT = (_PROJECT_ROOT / ".blackbase" / "runs" / RUN_ID).resolve()
RUN_ROOT = Path(os.environ.get("NSGABLACK_RUNTIME_COST_RUN_ROOT", str(_EXPECTED_RUN_ROOT)))
if not RUN_ROOT.is_absolute() or RUN_ROOT.resolve() != _EXPECTED_RUN_ROOT:
    raise ValueError("runtime cost RUN_ROOT must be the absolute Project/.blackbase/runs/RUN_ID directory")
RUN_ROOT = RUN_ROOT.resolve()
_PROFILED = bool(os.environ.get("NSGABLACK_RUNTIME_PROFILE_DIR"))
_WORKLOAD = os.environ.get("NSGABLACK_RUNTIME_COST_WORKLOAD", "bootstrap")
if _WORKLOAD not in {"bootstrap", "iteration"}:
    raise ValueError("unsupported diagnostic workload")
_ITERATION = _WORKLOAD == "iteration"
_PRODUCTION_CASE = Path(__file__).resolve().parent.parent / "production_scheduling" / "cases" / "production_scheduling"
_CAPABILITIES = ["production_inner", "nested_eval"]

L0 = {
    "namespace": "examples.runtime_cost_probe." + RUN_ID,
    "offer": {"threads": 1, "workers": 1, "gpus": 0, "backend": "local",
              "metadata": {"memory_mb": 1536}},
    "policy": {"mode": "strict", "max_workers": 1, "max_threads": 1,
               "max_gpus": 0, "max_memory_mb": 1536, "cpu_oversubscribe": False},
    "default_request": {"threads": 1, "workers": 1, "gpus": 0, "backend": "local",
                        "memory_mb": 1536, "capabilities": _CAPABILITIES},
    "lease_backend": "sqlite", "lease_path": str(RUN_ROOT / "leases.sqlite"),
    "lease_ttl_seconds": 30, "lease_heartbeat_seconds": 5,
    "control_path": str(RUN_ROOT / "controls.sqlite"),
    "control_active_ttl_seconds": 90, "control_heartbeat_seconds": 5,
    "budgets": {"evaluations": 97 if _ITERATION else 33, "audit_evaluations": 1},
    "artifacts": {"path": str(RUN_ROOT / "artifacts"), "allow_unsafe_serializers": False},
    "termination": {"mode": "cooperative_then_terminate", "grace_seconds": 2,
                    "kill_grace_seconds": 1, "poll_interval_seconds": .1},
}

PROBE_ARGV = [
    "--evaluation-only", "--machines", "22", "--materials", "157", "--days", "31",
    "--bom", str(_PRODUCTION_CASE / "machine_material_mapping.csv"),
    "--supply", str(_PRODUCTION_CASE / "SUPPLY.xlsx"),
    "--production-case-dir", str(_PRODUCTION_CASE),
    "--seed", "42", "--inner-seed", "42",
    "--inner-pop-size", "16", "--inner-generations", "8" if _ITERATION else "2", "--inner-max-evaluations", "96" if _ITERATION else "32",
    "--max-active-machines", "8", "--max-production-per-machine", "3000",
    "--outer-parallel-workers", "1", "--inner-parallel-workers", "1",
    "--inner-memory-mb", "768", "--nested-task-timeout-seconds", ("160" if _PROFILED else "80") if _ITERATION else ("70" if _PROFILED else "35"),
    "--no-decision-trace", "--no-profiler",
]

STAGES = [{
    "name": "probe", "cases": ["supply_adjustment_nested"], "mode": "build", "policy": "serial",
    # This absolute Case deadline also covers assembly, nested work and publication.
    "timeout_seconds": (180 if _PROFILED else 90) if _ITERATION else (80 if _PROFILED else 45),
    "component_overrides": {"supply_adjustment_nested": {"argv": PROBE_ARGV}},
}]
GROUPS = {"default": {"stages": ["probe"]}}
