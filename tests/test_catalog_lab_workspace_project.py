"""Source navigation stays bound to manifest paths and never executes a Project."""
from copy import deepcopy

import pytest

from nsgablack.catalog.lab_workspace_project import (
    MAX_OUTLINE_SOURCE_CHARS, project_outline, source_outline,
)


def manifest(*paths):
    return {"revision_id": "current", "files": [{"path": path} for path in paths]}


def test_case_outline_keeps_multiple_adapters_and_exact_case_scope():
    value = manifest("project_config.py", "run_project.py", "README.md",
        "cases/a/build_solver.py", "cases/a/run_solver.py", "cases/a/README.md",
        "cases/a/adapter/ga.py", "cases/a/adapter/vns.py", "cases/a/problem/model.py",
        "cases/a/pipeline/operators.py", "cases/a/bias/preference.py",
        "cases/a/plugins/logger.py", "cases/a/input.csv", "cases/a/config.py",
        "cases/a/unit/custom.py", "cases/b/build_solver.py", "cases/b/run_solver.py",
        "cases/incomplete/build_solver.py", "shared/supply.xlsx")
    before = deepcopy(value)
    outlined = project_outline(value)
    assert value == before
    assert outlined["scope"] == "manifest_only"
    assert outlined["case_names"] == ["a", "b"]
    case = outlined["cases"][0]
    assert case["default_path"] == "cases/a/README.md"
    assert case["readme_path"] == "cases/a/README.md"
    groups = {group["id"]: group for group in case["groups"]}
    assert groups["problem"]["paths"] == ["cases/a/input.csv", "cases/a/problem/model.py"]
    assert {"cases/a/adapter/ga.py", "cases/a/adapter/vns.py", "cases/a/unit/custom.py"} <= set(groups["algorithm"]["paths"])
    assert groups["pipeline"]["paths"] == ["cases/a/pipeline/operators.py"]
    assert groups["capability"]["paths"] == ["cases/a/bias/preference.py", "cases/a/plugins/logger.py"]
    assert all(path.startswith("cases/a/") for path in groups["all"]["paths"])
    assert "project_config.py" in outlined["project_paths"]
    assert "shared/supply.xlsx" in outlined["project_paths"]
    assert "cases/incomplete/build_solver.py" in outlined["project_paths"]
    assert outlined["cases"][1]["default_path"] == "cases/b/build_solver.py"


def test_standard_entry_pair_not_readme_or_nested_name_discovers_case():
    outlined = project_outline(manifest("README.md", "cases/a/README.md",
        "cases/nested/cases/a/build_solver.py", "cases/nested/cases/a/run_solver.py",
        "cases/only/build_solver.py", "cases/other/run_solver.py"))
    assert outlined["cases"] == []
    assert outlined["all_paths"] == outlined["project_paths"]


@pytest.mark.parametrize("path", ["../private.py", "/etc/secret", "C:/secret.py",
    "cases/a/../b.py", "cases\\a\\build_solver.py", "a//b.py", "./a.py", "a\x00.py"])
def test_manifest_path_validation_does_not_offer_host_paths(path):
    with pytest.raises(ValueError):
        project_outline(manifest(path))


@pytest.mark.parametrize("value", [None, {"files": "file.py"}, {"files": [None]}, {"files": [{"path": 4}]}])
def test_invalid_manifest_is_rejected(value):
    with pytest.raises(ValueError):
        project_outline(value)


def test_empty_and_duplicate_manifest_remain_deterministic():
    assert project_outline({})["all_paths"] == []
    assert project_outline(manifest("z.md", "A.md", "z.md"))["all_paths"] == ["A.md", "z.md"]


def test_source_outlines_definitions_and_real_calls_without_running_anything(tmp_path):
    marker = tmp_path / "never-created.txt"
    source = ("from nsgablack.adapters.search_plan import serial as sequence, repeat\n"
              "from nsgablack.adapters.pool_tasks import PoolTaskSpec as Task\n"
              "from pathlib import Path\n"
              f"Path({str(marker)!r}).write_text('must not execute')\n"
              "# adapter.set_change(fake)\n"
              "message = 'PoolTaskSpec() and serial()'\n"
              "class Custom:\n"
              "    async def choose(self, pool):\n"
              "        return pool.chosen(rule)\n"
              "def build_solver():\n"
              "    adapter.set_change(change)\n"
              "    adapter.set_pool_maintenance(keep_elite)\n"
              "    plan = repeat(times=3, body=sequence(stage('ga'), stage('vns')))\n"
              "    return Task(mode='refine')\n")
    outlined = source_outline("cases/search/build_solver.py", source)
    assert outlined["syntax_ok"] is True
    assert not marker.exists()
    assert [(item["name"], item["line"]) for item in outlined["symbols"]] == [
        ("Custom", 7), ("Custom.choose", 8), ("build_solver", 10)]
    assert outlined["symbols"][1]["kind"] == "async_function"
    assert all(item["line"] not in {5, 6} for item in outlined["calls"])
    sequence = next(item for item in outlined["calls"] if item["name"] == "sequence")
    assert sequence["canonical_name"] == "nsgablack.adapters.search_plan.serial"
    assert sequence["role"] == "串行编排调用"
    task = next(item for item in outlined["calls"] if item["name"] == "Task")
    assert task["canonical_name"] == "nsgablack.adapters.pool_tasks.PoolTaskSpec"
    assert task["owner"] == "build_solver"
    assert all(item["evidence"] == "source_call" for item in outlined["calls"])
    assert outlined["scope"] == "static_source"


def test_alias_scope_and_assignment_do_not_keep_a_rebound_import_claim():
    source = """import nsgablack.adapters.search_plan as plans
from nsgablack.adapters.pool_tasks import PoolTaskSpec as Task
def first():
    local = Task
    return local(mode='refine')
def second(Task):
    return Task()
Task = user_factory
Task()
plans.serial()
"""
    outlined = source_outline("adapter.py", source)
    calls = outlined["calls"]
    assert next(item for item in calls if item["name"] == "local")["canonical_name"].endswith("PoolTaskSpec")
    # Unknown callables are not inferred to be the earlier imported Task.
    assert not any(item["name"] == "Task" for item in calls)
    assert next(item for item in calls if item["name"] == "plans.serial")["canonical_name"] == "nsgablack.adapters.search_plan.serial"


def test_non_python_and_invalid_python_remain_readable_without_fake_definitions():
    text = source_outline("README.md", "# def build_solver():\nserial()")
    assert text == {"kind": "text", "syntax_ok": None, "symbols": [], "calls": [],
                    "diagnostics": [], "scope": "static_source"}
    invalid = source_outline("adapter.py", "def choose(:\n    return pool\n")
    assert invalid["syntax_ok"] is False
    assert invalid["symbols"] == invalid["calls"] == []
    assert invalid["diagnostics"][0]["code"] == "python-syntax-error"
    assert invalid["diagnostics"][0]["line"] == 1


def test_source_navigation_handles_unicode_bom_and_expression_receiver():
    outlined = source_outline("操作.py", "\ufeffdef 选择(pool):\n    return factory().set_change(rule)\n")
    assert outlined["symbols"][0]["name"] == "选择"
    assert outlined["calls"][0]["name"] == "<expression>.set_change"
    assert outlined["calls"][0]["canonical_name"] is None


def test_relative_import_location_is_not_rewritten_as_an_absolute_module():
    outlined = source_outline("build_solver.py", "from . import composition as c\nc.serial()\n")
    assert outlined["calls"][0]["canonical_name"] == ".composition.serial"


def test_large_source_is_bounded_without_running_a_parser():
    outlined = source_outline("large.py", "#" * (MAX_OUTLINE_SOURCE_CHARS + 1))
    assert outlined["syntax_ok"] is None
    assert outlined["diagnostics"][0]["code"] == "source-outline-too-large"
