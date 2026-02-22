from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from textwrap import dedent


def test_import_performance_module_when_numba_import_crashes():
    repo_root = Path(__file__).resolve().parents[1]
    code = dedent(
        """
        import builtins
        import numpy as np

        original_import = builtins.__import__

        def guarded_import(name, globals=None, locals=None, fromlist=(), level=0):
            if name == "numba" or str(name).startswith("numba."):
                raise RuntimeError("simulated numba import failure")
            return original_import(name, globals, locals, fromlist, level)

        builtins.__import__ = guarded_import

        import nsgablack.utils.performance as perf

        objectives = np.array([[1.0, 2.0], [2.0, 1.0], [3.0, 3.0]], dtype=float)
        fronts, ranks = perf.fast_non_dominated_sort_optimized(objectives)
        assert isinstance(fronts, list)
        assert ranks.shape[0] == 3
        print("ok")
        """
    )
    env = dict(os.environ)
    env["PYTHONPATH"] = str(repo_root) + os.pathsep + env.get("PYTHONPATH", "")
    proc = subprocess.run(
        [sys.executable, "-c", code],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
        env=env,
        timeout=60,
    )
    assert proc.returncode == 0, proc.stderr or proc.stdout
    assert "ok" in proc.stdout
