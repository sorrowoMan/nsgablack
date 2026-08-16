from __future__ import annotations

import inspect
import json
import os
from pathlib import Path
import subprocess
import sys

import numpy as np

from nsgablack.plugins.domain_backends.backend_contract import BackendSolveRequest
from nsgablack.plugins.domain_backends.mlblack_symbolic_consensus_backend import (
    MlblackSymbolicConsensusBackend,
    MlblackSymbolicConsensusBackendConfig,
)


def test_current_mlblack_symbolic_bridge_runs_and_inherits_parent_grant(tmp_path: Path) -> None:
    mlblack_root = Path(__file__).resolve().parents[2] / "mlblack"
    backend = MlblackSymbolicConsensusBackend(
        config=MlblackSymbolicConsensusBackendConfig(
            mlblack_root=str(mlblack_root),
            benchmark_key="ohm_like",
            n_total=32,
            output_root=str(tmp_path / "inner"),
            consensus_cycles=1,
            unlocked_runs_per_cycle=1,
            locked_runs_per_cycle=1,
            orth_candidate_limit=12,
            core_max_terms=2,
            inner_steps=1,
            inner_population_size=2,
            stage2_inner_steps=1,
            stage2_inner_population_size=2,
            cache_results=False,
        )
    )
    request = BackendSolveRequest(
        candidate=np.asarray([12.0, 4.0, 3.0, 2.0], dtype=float),
        eval_context={
            "generation": 0,
            "individual_id": 0,
            "resource_context": {
                "threads": 2,
                "namespace": "tests.outer",
                "grant": {"threads": 2, "workers": 2},
            },
        },
        inner_problem={
            "benchmark_key": "ohm_like",
            "unlocked_runs_per_cycle": 1,
            "locked_runs_per_cycle": 1,
        },
    )

    result = dict(backend.solve(request))

    assert result["status"] == "ok"
    assert result["protocol"] == "nsgablack_mlblack_symbolic_bridge_v3"
    assert result["total_inner_runs"] == 2
    assert result["resource_context"]["threads"] == 2
    assert result["resource_context"]["nested"] is True
    assert result["resource_context"]["namespace"] == "tests.outer.mlblack_inner"
    assert np.isfinite(float(result["best_test_rmse"]))
    assert len(result["objectives"]) == 4
    assert Path(result["summary_path"]).is_file()
    assert Path(result["comparison_path"]).is_file()
    assert Path(result["core_selection_path"]).is_file()


def test_symbolic_bridge_no_longer_imports_retired_mlblack_modules() -> None:
    source = inspect.getsourcefile(MlblackSymbolicConsensusBackend)
    assert source is not None
    text = Path(source).read_text(encoding="utf-8")

    assert "from config import" not in text
    assert "from training import" not in text
    assert "from workflow import" not in text


def test_symbolic_case_normal_cli_closes_the_current_bridge(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[1]
    entry = (
        root
        / "examples"
        / "cases"
        / "mlblack_symbolic_consensus_scaffold"
        / "cases"
        / "mlblack_symbolic_consensus_scaffold"
        / "run_solver.py"
    )
    env = os.environ.copy()
    env["NSGABLACK_RESOURCE_CONTEXT_JSON"] = json.dumps(
        {
            "threads": 2,
            "namespace": "tests.symbolic",
            "grant": {"threads": 2, "workers": 2},
        }
    )
    completed = subprocess.run(
        [
            sys.executable,
            str(entry),
            "--outer-adapter",
            "vns",
            "--generations",
            "1",
            "--pop-size",
            "4",
            "--batch-size",
            "4",
            "--n-total",
            "32",
            "--consensus-cycles",
            "1",
            "--unlocked-runs-per-cycle",
            "1",
            "--locked-runs-per-cycle",
            "1",
            "--inner-fit-steps",
            "1",
            "--inner-fit-population",
            "2",
            "--task-fit-steps",
            "1",
            "--task-fit-population",
            "2",
            "--run-dir",
            str(tmp_path / "run"),
            "--no-logs",
        ],
        cwd=root,
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    assert '[resource-context] {"grant": {"threads": 2, "workers": 2}' in completed.stdout
    assert "[case] status=ok steps=1" in completed.stdout
    assert "[case] best_inner" in completed.stdout
    assert "[case] summary=" in completed.stdout
