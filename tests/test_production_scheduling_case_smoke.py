from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def test_production_scheduling_case_runs_quickly():
    repo_root = Path(__file__).resolve().parents[1]
    script = repo_root / "examples" / "cases" / "production_scheduling" / "working_integrated_optimizer.py"
    assert script.exists()

    # Keep the smoke test small and dependency-light:
    # - --no-export avoids pandas/openpyxl requirement
    # - thread backend avoids Windows process spawn cost in CI
    cmd = [
        sys.executable,
        str(script),
        "--machines",
        "4",
        "--materials",
        "10",
        "--days",
        "5",
        "--pop-size",
        "16",
        "--generations",
        "2",
        "--no-export",
        "--no-run-logs",
        "--parallel-backend",
        "thread",
        "--parallel-workers",
        "1",
        "--seed",
        "1",
    ]

    subprocess.run(cmd, cwd=str(repo_root), check=True, timeout=180)

