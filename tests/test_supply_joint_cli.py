"""Case CLI 必须保留正式 Project runtime，检查不能启动求解。"""

from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

import pytest


REPO = Path(__file__).resolve().parents[1]
PROJECT = REPO / "examples/cases/supply_adjustment_nested"
ENTRY = PROJECT / "cases/supply_adjustment_nested/run_solver.py"
ARGV_ENV = "NSGABLACK_SUPPLY_CASE_ARGV"


@pytest.fixture
def cli():
    spec = importlib.util.spec_from_file_location("supply_joint_cli_under_test", ENTRY)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("previous", [None, '["--seed", "88"]'])
def test_normal_cli_delegates_exact_arguments_and_restores_prior_input(cli, monkeypatch, previous):
    if previous is None:
        monkeypatch.delenv(ARGV_ENV, raising=False)
    else:
        monkeypatch.setenv(ARGV_ENV, previous)
    args = ["--seed", "17", "--run-dir", "包含空格的 路径", "--evaluation-only"]
    observed = []

    def execute(root, **kwargs):
        observed.append((root, kwargs, json.loads(os.environ[ARGV_ENV])))
        return SimpleNamespace(status="succeeded", exit_code=0)

    def refuse_build(*args, **kwargs):
        pytest.fail("normal CLI must let Project assemble and inject its runtime")

    monkeypatch.setattr(cli, "execute_project", execute)
    monkeypatch.setattr(cli, "build_case", refuse_build)
    assert cli.main(args) == 0
    assert observed == [(PROJECT, {"group": "direct", "framework": "nsgablack"}, args)]
    assert os.environ.get(ARGV_ENV) == previous


def test_failed_project_status_and_exception_are_not_hidden(cli, monkeypatch):
    monkeypatch.setenv(ARGV_ENV, "[]")
    monkeypatch.setattr(cli, "execute_project", lambda *args, **kwargs: SimpleNamespace(status="failed", exit_code=7))
    assert cli.main(["--seed", "1"]) == 7
    assert os.environ[ARGV_ENV] == "[]"

    def fail(*args, **kwargs):
        raise RuntimeError("nested publication failed")

    monkeypatch.setattr(cli, "execute_project", fail)
    with pytest.raises(RuntimeError, match="nested publication failed"):
        cli.main(["--seed", "2"])
    assert os.environ[ARGV_ENV] == "[]"


def test_project_direct_group_consumes_cli_arguments_in_build_mode(monkeypatch):
    args = ["--inner-seed", "43", "--evaluation-only"]
    monkeypatch.setenv(ARGV_ENV, json.dumps(args))
    monkeypatch.setenv("BLACKBASE_JOINT_REDIS_URL", "")
    spec = importlib.util.spec_from_file_location("supply_joint_project_cli_contract", PROJECT / "project_config.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.GROUPS["direct"]["stages"] == ["direct"]
    direct = next(stage for stage in module.STAGES if stage["name"] == "direct")
    assert direct["mode"] == "build"
    assert direct["cases"] == ["supply_adjustment_nested"]
    assert direct["component_overrides"]["supply_adjustment_nested"]["argv"][-len(args):] == args


def test_check_uses_scoped_builder_and_closes_without_executing(cli, monkeypatch):
    case, builder = object(), object()
    observed = []
    resource = {"threads": 2, "namespace": "joint-cli-check"}
    monkeypatch.setattr(cli, "load_resource_context_from_env", lambda framework: resource)
    monkeypatch.setattr(cli, "load_case_builder", lambda root, name: builder if (root, name) == (PROJECT, "supply_adjustment_nested") else None)
    monkeypatch.setattr(cli, "build_case", lambda value, **kwargs: observed.append((value, kwargs)) or case)
    monkeypatch.setattr(cli, "print_case_check", lambda value: observed.append(("checked", value)))
    monkeypatch.setattr(cli, "close_case_after_build_check", lambda value: observed.append(("closed", value)))
    monkeypatch.setattr(cli, "execute_project", lambda *args, **kwargs: pytest.fail("build check must not execute Project"))
    args = ["--check", "--inner-parallel-workers", "8"]
    assert cli.main(args) == 0
    assert observed == [(builder, {"resource_context": resource, "component_overrides": {"argv": args}}),
                        ("checked", case), ("closed", case)]


def test_script_check_works_outside_project_and_creates_no_run_output(tmp_path):
    output = tmp_path / "not-created"
    env = os.environ.copy()
    env["NSGABLACK_RESOURCE_CONTEXT_JSON"] = json.dumps({
        "threads": 2, "namespace": "joint-cli-check", "grant": {"threads": 2, "workers": 2}})
    result = subprocess.run([
        sys.executable, "-B", str(ENTRY), "--check", "--run-dir", str(output),
        "--outer-parallel-workers", "4", "--inner-parallel-workers", "8"],
        cwd=tmp_path, env=env, capture_output=True, text=True, timeout=30, check=False)
    assert result.returncode == 0, result.stderr
    assert "[check]" in result.stdout
    assert "threads=2 outer_workers=4->2 inner_workers=8->1" in result.stdout
    assert ("outer_backend=project_case outer_workers_requested=2 placement=local "
            "inner_backend=thread inner_workers_requested=1") in result.stdout
    assert not output.exists()
    assert not (tmp_path / ".blackbase").exists()
