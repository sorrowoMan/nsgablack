from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from blackbase.project.runtime import path_declares_check_argument


ROOT = Path(__file__).resolve().parents[1]
EXAMPLE_CASES = ROOT / "examples" / "cases"
RUN_ENTRIES = tuple(sorted(EXAMPLE_CASES.glob("*/cases/*/run_solver.py")))


def test_every_standard_case_cli_declares_build_check_contract():
    assert RUN_ENTRIES
    missing = [path for path in RUN_ENTRIES if not path_declares_check_argument(path)]
    assert missing == []


def test_standard_case_clis_do_not_call_removed_return_dict_mode():
    stale = [
        path
        for path in RUN_ENTRIES
        if "run(return_dict=True)" in path.read_text(encoding="utf-8")
    ]
    assert stale == []


@pytest.mark.parametrize("entry", RUN_ENTRIES, ids=lambda path: path.parent.name)
def test_every_standard_case_build_check_is_side_effect_bounded(entry: Path):
    completed = subprocess.run(
        [sys.executable, str(entry), "--check"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    assert "[check]" in completed.stdout
