from __future__ import annotations

import runpy
from pathlib import Path


def test_authoritative_examples_import_and_execute_smoke():
    # These are "fact standard" examples. Keep them runnable.
    root = Path(__file__).resolve().parents[1]
    examples = [
        root / "examples" / "blank_solver_plugin_demo.py",
        root / "examples" / "blank_vs_composable_demo.py",
        root / "examples" / "composable_solver_fusion_demo.py",
    ]

    for p in examples:
        ns = runpy.run_path(str(p), run_name="__main__")
        assert isinstance(ns, dict)

