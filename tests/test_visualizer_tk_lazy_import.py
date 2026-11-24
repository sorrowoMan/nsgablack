from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from textwrap import dedent

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]


def test_viz_import_is_headless_safe_and_ui_call_is_clear(tmp_path):
    (tmp_path / "tkinter.py").write_text(
        "raise ModuleNotFoundError(\"No module named 'tkinter'\", name='tkinter')\n",
        encoding="utf-8",
    )
    code = dedent(
        """
        import os
        import nsgablack.utils.viz as viz

        os.environ.pop("NSGABLACK_TEST_UI", None)
        assert viz.maybe_launch_ui(lambda: None, env_var="NSGABLACK_TEST_UI") is False
        try:
            viz.launch_empty()
        except RuntimeError as exc:
            assert "does not provide tkinter/Tcl-Tk" in str(exc)
        else:
            raise AssertionError("launch_empty() should fail clearly without tkinter")
        print("headless-import-ok")
        """
    )
    env = dict(os.environ)
    paths = [str(tmp_path), str(REPO_ROOT.parent)]
    if env.get("PYTHONPATH"):
        paths.append(env["PYTHONPATH"])
    env["PYTHONPATH"] = os.pathsep.join(paths)
    proc = subprocess.run(
        [sys.executable, "-c", code],
        cwd=str(tmp_path),
        capture_output=True,
        text=True,
        env=env,
        timeout=60,
    )
    assert proc.returncode == 0, proc.stderr or proc.stdout
    assert "headless-import-ok" in proc.stdout


def test_visualizer_loader_does_not_mask_other_import_errors(monkeypatch):
    from nsgablack.utils.viz import visualizer_tk

    def fake_import_module(name: str):
        if name == "tkinter":
            return object()
        raise ImportError("simulated app dependency failure", name="other_dependency")

    monkeypatch.setattr(visualizer_tk.importlib, "import_module", fake_import_module)

    with pytest.raises(ImportError, match="simulated app dependency failure"):
        visualizer_tk.launch_empty()
