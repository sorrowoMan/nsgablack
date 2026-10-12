from __future__ import annotations

from nsgablack.project import run_project_doctor
import ast
import pytest
from nsgablack.project.doctor_core.rules.broad_except import _handler_body_is_swallow


@pytest.mark.parametrize("statement,swallowed", [
    ("return None", True),
    ("return {'ok': True}", True),
    ("return {'ok': False}", True),
    ("return {'ok': False, 'error': ''}", True),
    ("return {'ok': False, 'error': 'failed to read'}", False),
    ("return {'ok': False, 'error': str(exc)}", False),
    ("return Result(is_valid=False, error_message=str(exc))", False),
    ("raise", False),
    ("report_soft_error(exc=exc)", False),
])
def test_failure_evidence_is_distinct_from_a_silent_fallback(statement, swallowed):
    tree = ast.parse("try:\n    execute()\nexcept Exception as exc:\n    " + statement)
    handler = tree.body[0].handlers[0]
    assert _handler_body_is_swallow(handler.body, handler.name) is swallowed


def test_doctor_flags_broad_except_swallow_in_core_as_error(tmp_path):
    (tmp_path / ".case").write_text("kind = solver\n", encoding="utf-8")
    (tmp_path / "build_solver.py").write_text("def build_solver():\n    return None\n", encoding="utf-8")
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
    (tmp_path / ".case").write_text("kind = solver\n", encoding="utf-8")
    (tmp_path / "build_solver.py").write_text("def build_solver():\n    return None\n", encoding="utf-8")
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
