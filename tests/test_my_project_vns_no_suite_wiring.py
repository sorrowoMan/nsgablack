from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]


def _run_build_solver_check(*extra: str) -> str:
    script = _REPO_ROOT / "my_project" / "build_solver.py"
    env = dict(os.environ)
    paths = env.get("PYTHONPATH", "").split(os.pathsep) if env.get("PYTHONPATH") else []
    if str(_REPO_ROOT) not in paths:
        paths.insert(0, str(_REPO_ROOT))
    env["PYTHONPATH"] = os.pathsep.join(paths)
    cmd = [sys.executable, str(script), "--check", *extra]
    out = subprocess.run(
        cmd,
        cwd=str(_REPO_ROOT),
        capture_output=True,
        text=True,
        check=True,
        env=env,
    )
    return out.stdout.strip()


def test_my_project_default_strategy_is_vns():
    output = _run_build_solver_check("--quickstart")
    assert output, f"Expected output, got: {output}"
    assert "adapter=" in output


def test_my_project_vns_strategy_wires_without_suite_entrypoint():
    output = _run_build_solver_check("--strategy", "vns", "--quickstart")
    assert "adapter=" in output
    assert "quickstart=ok" in output

