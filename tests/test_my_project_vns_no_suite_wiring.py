from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def _run_build_solver_check(*extra: str) -> str:
    root = Path(__file__).resolve().parents[1]
    script = root / "my_project" / "build_solver.py"
    cmd = [sys.executable, str(script), "--check", *extra]
    out = subprocess.run(
        cmd,
        cwd=str(root),
        capture_output=True,
        text=True,
        check=True,
    )
    return out.stdout.strip()


def test_my_project_default_strategy_is_nsga2():
    output = _run_build_solver_check("--quickstart")
    assert "adapter=NSGA2Adapter" in output


def test_my_project_vns_strategy_wires_without_suite_entrypoint():
    output = _run_build_solver_check("--strategy", "vns", "--quickstart")
    assert "adapter=VNSAdapter" in output
    assert "mutator=ContextGaussianMutation" in output

