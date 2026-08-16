from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
EXAMPLE_CASES = ROOT / "examples" / "cases"


def test_every_standard_case_cli_declares_build_check_contract():
    run_entries = sorted(EXAMPLE_CASES.glob("*/cases/*/run_solver.py"))
    assert run_entries
    missing = [path for path in run_entries if "--check" not in path.read_text(encoding="utf-8")]
    assert missing == []


@pytest.mark.parametrize(
    "relative_entry",
    (
        "examples/cases/arima_order_search/cases/arima_order_search/run_solver.py",
        "examples/cases/l0_distributed_worker/cases/l0_distributed_worker/run_solver.py",
        "examples/cases/supply_adjustment_nested/cases/supply_adjustment_nested/run_solver.py",
    ),
)
def test_divergent_legacy_case_build_checks_are_side_effect_bounded(relative_entry: str):
    completed = subprocess.run(
        [sys.executable, str(ROOT / relative_entry), "--check"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    assert "[check]" in completed.stdout
