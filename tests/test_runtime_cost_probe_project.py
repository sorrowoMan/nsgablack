"""Configuration and factory routing only; never run the production model."""

import importlib.util
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest


REPO = Path(__file__).resolve().parents[1]
PROJECT = REPO / "examples/cases/runtime_cost_probe"
SOURCE_PROJECT = REPO / "examples/cases/supply_adjustment_nested"


def load_file(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_config(monkeypatch, run_id="configuration-test"):
    monkeypatch.setenv("NSGABLACK_RUNTIME_COST_RUN_ID", run_id)
    monkeypatch.setenv("NSGABLACK_RUNTIME_COST_RUN_ROOT", str(PROJECT / ".blackbase/runs" / run_id))
    return load_file(PROJECT / "project_config.py", "runtime_cost_probe_configuration")


def option(argv, name):
    assert argv.count(name) == 1
    return argv[argv.index(name) + 1]


def test_probe_has_bounded_original_model_configuration_and_local_authorities(monkeypatch):
    config = load_config(monkeypatch)
    stage, = config.STAGES
    assert config.GROUPS == {"default": {"stages": ["probe"]}}
    assert stage["cases"] == ["supply_adjustment_nested"] and stage["mode"] == "build"
    assert stage["timeout_seconds"] == 45
    assert config.L0["budgets"] == {"evaluations": 33, "audit_evaluations": 1}
    assert config.L0["namespace"] == "examples.runtime_cost_probe.configuration-test"
    assert config.L0["offer"]["threads"] == config.L0["policy"]["max_threads"] == 1
    assert config.L0["offer"]["gpus"] == 0
    assert config.L0["default_request"]["memory_mb"] == 1536
    assert config.L0["lease_backend"] == "sqlite"
    assert Path(config.L0["lease_path"]).parent == config.RUN_ROOT
    assert Path(config.L0["control_path"]).parent == config.RUN_ROOT
    assert Path(config.L0["artifacts"]["path"]).parent == config.RUN_ROOT
    argv = stage["component_overrides"]["supply_adjustment_nested"]["argv"]
    assert "--evaluation-only" in argv and "--parallel" not in argv
    assert "--no-profiler" in argv and "--no-decision-trace" in argv
    for flag, value in {"--machines": "22", "--materials": "157", "--days": "31",
                        "--inner-pop-size": "16", "--inner-generations": "2",
                        "--inner-max-evaluations": "32", "--inner-memory-mb": "768",
                        "--inner-parallel-workers": "1", "--max-production-per-machine": "3000",
                        "--nested-task-timeout-seconds": "35"}.items():
        assert option(argv, flag) == value
    production = REPO / "examples/cases/production_scheduling/cases/production_scheduling"
    assert Path(option(argv, "--production-case-dir")) == production
    assert Path(option(argv, "--bom")) == production / "machine_material_mapping.csv"
    assert Path(option(argv, "--supply")) == production / "SUPPLY.xlsx"


@pytest.mark.parametrize("run_id", ["../escape", "a/b", "", "a" * 65])
def test_run_identifier_cannot_escape_the_project_namespace(monkeypatch, run_id):
    with pytest.raises(ValueError, match="safe identifier"):
        load_config(monkeypatch, run_id)


def test_output_root_follows_shared_project_authority_and_recorder_contract(monkeypatch, tmp_path):
    monkeypatch.setenv("NSGABLACK_RUNTIME_COST_RUN_ID", "configuration-test")
    monkeypatch.setenv("NSGABLACK_RUNTIME_COST_RUN_ROOT", str(tmp_path))
    with pytest.raises(ValueError, match="Project/.blackbase/runs/RUN_ID"):
        load_file(PROJECT / "project_config.py", "runtime_cost_probe_wrong_root")


@pytest.mark.parametrize("case_name", ["supply_adjustment_nested", "production_inner"])
def test_thin_factory_uses_public_canonical_assembly_and_forwards_context(monkeypatch, case_name):
    monkeypatch.delenv("NSGABLACK_RUNTIME_PROFILE_DIR", raising=False)
    module = load_file(PROJECT / "cases" / case_name / "build_solver.py", "probe_factory_" + case_name)
    builder, case = object(), object()
    context = {"threads": 1, "metadata": {"source": "Project L0"}}
    overrides = {"task": {"assembly_only": True}} if case_name == "production_inner" else {"argv": ["--check"]}
    calls = []

    def load(source, name):
        calls.append((source, name))
        return builder

    def build(value, *, resource_context, component_overrides):
        assert value is builder
        assert resource_context is context and component_overrides is overrides
        return case

    monkeypatch.setattr(module, "load_case_builder", load)
    monkeypatch.setattr(module, "build_case", build)
    assert module.build_solver(resource_context=context, component_overrides=overrides) is case
    assert calls == [(SOURCE_PROJECT, case_name)]


@pytest.mark.parametrize("case_name", ["supply_adjustment_nested", "production_inner"])
def test_optional_profile_starts_after_canonical_assembly_only(monkeypatch, case_name):
    module = load_file(PROJECT / "cases" / case_name / "build_solver.py", "probe_profile_" + case_name)
    case, events = object(), []
    monkeypatch.setattr(module, "load_case_builder", lambda *args: object())
    monkeypatch.setattr(module, "build_case", lambda *args, **kwargs: events.append("assembled") or case)
    monkeypatch.setitem(sys.modules, "sitecustomize", SimpleNamespace(start_profile=lambda: events.append("profile")))
    monkeypatch.delenv("NSGABLACK_RUNTIME_PROFILE_DIR", raising=False)
    assert module.build_solver() is case
    assert events == ["assembled"]
    events.clear()
    monkeypatch.setenv("NSGABLACK_RUNTIME_PROFILE_DIR", "requested-profile-dir")
    assert module.build_solver() is case
    assert events == ["assembled", "profile"]


@pytest.mark.parametrize("case_name", ["supply_adjustment_nested", "production_inner"])
def test_requested_profile_without_site_hook_fails_explicitly(monkeypatch, case_name):
    module = load_file(PROJECT / "cases" / case_name / "build_solver.py", "probe_missing_profile_" + case_name)
    events = []
    monkeypatch.setattr(module, "load_case_builder", lambda *args: object())
    monkeypatch.setattr(module, "build_case", lambda *args, **kwargs: events.append("assembled") or object())
    monkeypatch.delitem(sys.modules, "sitecustomize", raising=False)
    monkeypatch.setenv("NSGABLACK_RUNTIME_PROFILE_DIR", "requested-profile-dir")
    with pytest.raises(RuntimeError, match=r"requires sitecustomize.start_profile\(\)"):
        module.build_solver()
    assert events == ["assembled"]


def test_formal_child_name_resolves_under_diagnostic_project():
    from blackbase.project import CaseExecutor, load_case_builder

    executor = CaseExecutor(PROJECT)
    child = load_case_builder(executor.project_root, "production_inner")
    assert child.project_root == PROJECT and child.case_name == "production_inner"
    assert child.accepts_parameter("resource_context") and child.accepts_parameter("component_overrides")
    assert not (PROJECT / "cases/production_inner/problem/production_problem.py").exists()


def test_project_entry_uses_shared_runner_and_the_same_run_identifier(monkeypatch):
    import nsgablack.project.project_runner as runner

    module = load_file(PROJECT / "run_project.py", "runtime_cost_probe_entry")
    monkeypatch.setenv("NSGABLACK_RUNTIME_COST_RUN_ID", "entry-test")
    calls = []
    monkeypatch.setattr(runner, "main", lambda **kwargs: calls.append(kwargs) or 7)
    assert module.main(["--check", "--build-check"]) == 7
    assert calls == [{"project_root": PROJECT, "argv": ["--check", "--build-check", "--run-id", "entry-test"]}]
    with pytest.raises(ValueError, match="must equal"):
        module.main(["--check", "--run-id=other-run"])
