from __future__ import annotations

from nsgablack.project import run_project_doctor


def test_doctor_flags_broad_except_swallow_in_core_as_error(tmp_path):
    core_dir = tmp_path / "core"
    core_dir.mkdir(parents=True)
    (core_dir / "demo.py").write_text(
        "def f():\n"
        "    try:\n"
        "        return 1\n"
        "    except Exception:\n"
        "        pass\n",
        encoding="utf-8",
    )

    report = run_project_doctor(tmp_path, instantiate_solver=False, strict=False)
    rows = [d for d in report.diagnostics if d.code == "broad-except-swallow-core"]
    assert rows
    assert all(d.level == "error" for d in rows)


def test_doctor_flags_broad_except_swallow_in_non_core_as_warn(tmp_path):
    plugin_dir = tmp_path / "plugins"
    plugin_dir.mkdir(parents=True)
    (plugin_dir / "demo.py").write_text(
        "def g():\n"
        "    try:\n"
        "        return 1\n"
        "    except Exception:\n"
        "        return None\n",
        encoding="utf-8",
    )

    report = run_project_doctor(tmp_path, instantiate_solver=False, strict=False)
    rows = [d for d in report.diagnostics if d.code == "broad-except-swallow"]
    assert rows
    assert all(d.level == "warn" for d in rows)

