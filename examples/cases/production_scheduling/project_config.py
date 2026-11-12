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


# Quality experiments are separate, explicitly named Project groups.  The
# original main/default smoke profile above remains unchanged.
import os
from pathlib import Path
import re

_PROJECT_ROOT = Path(__file__).resolve().parent
_QUALITY_SESSION = os.environ.get("NSGABLACK_PRODUCTION_QUALITY_RUN_ID", "direct")
if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,99}", _QUALITY_SESSION):
    raise ValueError("NSGABLACK_PRODUCTION_QUALITY_RUN_ID must be a single run identifier")
_QUALITY_ROOT = _PROJECT_ROOT / "results" / "quality" / _QUALITY_SESSION
_RESUME_CHECKPOINT = os.environ.get("NSGABLACK_PRODUCTION_RESUME_CHECKPOINT", "").strip()
_CASE_ROOT = _PROJECT_ROOT / "cases" / "production_scheduling"


def _quality_stage(method: str, seed: int, *, pilot: bool = False) -> dict:
    name = f"quality_{'pilot' if pilot else method}_s{seed}"
    folder = _QUALITY_ROOT / name
    argv = [
        "--machines", "22", "--materials", "157", "--days", "31",
        "--bom", str(_CASE_ROOT / "machine_material_mapping.csv"),
        "--supply", str(_CASE_ROOT / "SUPPLY.xlsx"),
        "--pop-size", "32" if pilot else "64",
        "--max-evaluations", "300" if pilot else "2500",
        "--seed", str(seed), "--parallel-backend", "thread", "--parallel-workers", "1",
        "--pareto-export", "12", "--sanity-check-export", "--no-run-logs",
        "--report-every", "5", "--run-id", name,
        "--export", str(folder / "exports" / "plan.csv"),
    ]
    if method == "greedy":
        argv += ["--solver", "baseline-greedy", "--generations", "1"]
    elif method == "aco":
        argv += ["--solver", "baseline-aco", "--aco-ants", "32", "--generations", "80"]
    else:
        argv += ["--solver", "multi-agent", "--cooperation", method,
                 "--moead-pop-size", "16" if pilot else "48",
                 "--moead-neighborhood", "8" if pilot else "20",
                 "--vns-batch-size", "8" if pilot else "16"]
        if method == "directional":
            argv += ["--quality-cycles", "1" if pilot else "2",
                     "--explore-steps", "4" if pilot else "12",
                     "--refine-steps", "3" if pilot else "5",
                     "--refine-directions", "4" if pilot else "8",
                     "--objective-output-scale", "100000",
                     "--generations", "64" if pilot else "256"]
            if not pilot or _RESUME_CHECKPOINT:
                checkpoint_dir = Path(_RESUME_CHECKPOINT).resolve().parent if _RESUME_CHECKPOINT else folder / "checkpoints"
                argv += ["--checkpoint-dir", str(checkpoint_dir),
                         "--checkpoint-every", "10"]
                if _RESUME_CHECKPOINT:
                    argv += ["--resume", _RESUME_CHECKPOINT]
        else:
            argv += ["--generations", "100"]
    return {"name": name, "cases": ["production_scheduling"], "policy": "serial", "mode": "build",
            "timeout_seconds": 900,
            "resource_requests": {"production_scheduling": {"threads": 1, "gpus": 0, "backend": "local"}},
            "component_overrides": {"production_scheduling": {"argv": argv}}}


for _seed in (42, 43, 44):
    for _method in ("greedy", "aco", "phased", "directional"):
        _stage = _quality_stage(_method, _seed)
        STAGES.append(_stage)
        GROUPS[_stage["name"]] = {"stages": [_stage["name"]]}
_pilot = _quality_stage("directional", 42, pilot=True)
STAGES.append(_pilot)
GROUPS[_pilot["name"]] = {"stages": [_pilot["name"]]}

# Fixed-budget ablations reuse this Case and the same quality candidate pipeline.
_ABLATION_SESSION = os.environ.get("NSGABLACK_PRODUCTION_ABLATION_RUN_ID", "direct")
_ABLATION_MUTATION_ATTEMPTS = int(os.environ.get("NSGABLACK_PRODUCTION_MUTATION_ATTEMPTS", "1"))
if not 1 <= _ABLATION_MUTATION_ATTEMPTS <= 8:
    raise ValueError("ablation mutation attempts must be in [1, 8]")
if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,79}", _ABLATION_SESSION):
    raise ValueError("invalid ablation run identifier")
for _profile, _budget in (("pilot", 240), ("formal", 1104)):
    for _seed in (42, 43, 44):
        for _arm in ("constructive", "moead", "directional"):
            _name = f"ablation_{_profile}_{_arm}_s{_seed}"
            _folder = _PROJECT_ROOT / "results" / "ablation" / _ABLATION_SESSION / _name
            _argv = ["--machines", "22", "--materials", "157", "--days", "31",
                "--bom", str(_CASE_ROOT / "machine_material_mapping.csv"), "--supply", str(_CASE_ROOT / "SUPPLY.xlsx"),
                "--cooperation", _arm, "--seed", str(_seed), "--pop-size", "64", "--moead-pop-size", "48",
                "--moead-neighborhood", "20", "--vns-batch-size", "16", "--generations", "256",
                "--max-evaluations", str(_budget), "--quality-cycles", "4" if _profile == "pilot" else "1",
                "--explore-steps", "1" if _profile == "pilot" else "12",
                "--refine-steps", "3" if _profile == "pilot" else "5",
                "--refine-directions", "2" if _profile == "pilot" else "8",
                "--parallel-backend", "thread", "--parallel-workers", "1", "--no-run-logs",
                "--pareto-archive-update-every", "1", "--pareto-export", "12", "--sanity-check-export",
                "--ablation-audit", "--mutation-attempts", str(_ABLATION_MUTATION_ATTEMPTS),
                "--export", str(_folder / "exports" / "plan.csv")]
            STAGES.append({"name": _name, "cases": ["production_scheduling"], "mode": "build", "policy": "serial",
                "timeout_seconds": 900,
                "resource_requests": {"production_scheduling": {"threads": 1, "gpus": 0, "backend": "local"}},
                "component_overrides": {"production_scheduling": {"argv": _argv}}})
            GROUPS[_name] = {"stages": [_name]}
