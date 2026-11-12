"""Typed Case parameters and genuine Project/L0 trial evidence."""
from __future__ import annotations

import hashlib
import base64
import io
import json
import os
from pathlib import Path
from types import SimpleNamespace
from zipfile import ZipFile

import pytest

from nsgablack.catalog import lab_project_trial as trial
from nsgablack.catalog.lab_jobs import spec_digest
from nsgablack.catalog.lab_project import export_project, normalize_spec
from nsgablack.catalog.lab_project_sources import ProjectSourceRegistry


@pytest.fixture
def project(tmp_path):
    project = export_project(normalize_spec({"recipe": "ga", "max_steps": 2,
        "population_size": 4, "initial_count": 8}), tmp_path / "examples" / "small")
    case = project / "cases" / "search"
    (case / "build_solver.py").rename(case / "_base_build_solver.py")
    (case / "build_solver.py").write_text('''import argparse
from ._base_build_solver import build_solver as _base

def build_parser():
    parser = argparse.ArgumentParser()
    parser.add_argument("--strength", type=float, default=0.2, help="Existing preference weight")
    parser.add_argument("--size", type=int, default=4)
    parser.add_argument("--method", choices=["native", "local"], default="native")
    parser.add_argument("--generations", type=int, default=2)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--output", type=str, default=None)
    parser.add_argument("--parallel-workers", type=int, default=6)
    parser.add_argument("--allow-infeasible-update", action="store_true")
    return parser

def build_solver(*args, component_overrides=None, **kwargs):
    build_parser().parse_args((component_overrides or {}).get("argv", []))
    return _base(*args, component_overrides={}, **kwargs)
''', encoding="utf-8")
    sources = ProjectSourceRegistry({"examples": project.parent})
    return project, sources


def proposal(sources):
    return {"schema": trial.PROPOSAL_SCHEMA, "project_id": "examples:small",
            "project_revision": sources.snapshot_manifest("examples:small")["source_digest"],
            "case_name": "search", "parameters": {"strength": 0.3},
            "budget": {"max_steps": 2, "timeout_seconds": 60, "threads": 1, "gpus": 0}, "seed": 42}


def test_parameter_contract_reads_literals_without_importing_builder(project):
    root, sources = project
    path = root / "cases" / "search" / "build_solver.py"
    path.write_text("raise RuntimeError('reading must not execute this')\n" + path.read_text(), encoding="utf-8")
    schema = trial.project_parameter_schema(sources, "examples:small", "search")
    assert schema["properties"]["strength"]["default"] == 0.2
    assert schema["properties"]["method"]["choices"] == ["native", "local"]
    assert {"output", "seed", "generations", "parallel_workers", "allow_infeasible_update"}.isdisjoint(schema["properties"])
    assert schema["parameter_sources"][0]["sha256"] == hashlib.sha256(path.read_bytes()).hexdigest()


def test_parameter_schema_uses_source_manifest_instead_of_hidden_or_secret_parsers(project):
    root, sources = project
    case = root / "cases" / "search"
    poison = '''import argparse
def build_parser():
    parser = argparse.ArgumentParser()
    parser.add_argument("--stolen", choices=["private-marker"], default="private-marker")
    return parser
'''
    for relative in ("secrets/cli.py", ".hidden/cli.py", "credentials.py"):
        path = case / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(poison, encoding="utf-8")
    sensitive = case / "apparently_normal.py"
    sensitive.write_text("api_key = 'private-content-marker'\n" + poison, encoding="utf-8")
    schema = trial.project_parameter_schema(sources, "examples:small", "search")
    encoded = json.dumps(schema)
    assert "strength" in schema["properties"]
    assert "stolen" not in schema["properties"]
    assert "private-marker" not in encoded and "private-content-marker" not in encoded
    assert all("build_solver.py" == row["path"] for row in schema["parameter_sources"])


@pytest.mark.parametrize("parameters,code", [
    ({"strength": "0.3"}, "project_parameter_type"),
    ({"size": True}, "project_parameter_type"),
    ({"strength": float("nan")}, "project_parameter_bounds"),
    ({"method": "arbitrary"}, "project_parameter_choice"),
    ({"output": "../../outside"}, "project_parameter_unknown"),
    ({"parallel_workers": 8}, "project_parameter_unknown"),
    ({"allow_infeasible_update": True}, "project_parameter_unknown"),
])
def test_proposal_rejects_untyped_unknown_or_runtime_owned_parameters(project, parameters, code):
    _, sources = project
    value = proposal(sources)
    value["parameters"] = parameters
    with pytest.raises(trial.TrialError) as error:
        trial.validate_project_proposal(sources, value)
    assert error.value.code == code


@pytest.mark.parametrize("budget", [
    {"max_steps": 0}, {"max_steps": 10000}, {"max_steps": True},
    {"threads": 2}, {"gpus": 1}, {"threads": True},
    {"timeout_seconds": 181}, {"timeout_seconds": float("inf")},
])
def test_proposal_preserves_bounded_cpu_only_execution(project, budget):
    _, sources = project
    value = proposal(sources)
    value["budget"] = budget
    with pytest.raises(trial.TrialError) as error:
        trial.validate_project_proposal(sources, value)
    assert error.value.code == "invalid_project_budget"


def test_changed_source_or_data_requires_a_new_proposal(project):
    root, sources = project
    value = proposal(sources)
    (root / "cases" / "search" / "new_data.csv").write_text("item,amount\na,3\n", encoding="utf-8")
    with pytest.raises(trial.TrialError) as error:
        trial.validate_project_proposal(sources, value)
    assert error.value.code == "project_revision_changed"


def test_confirmation_is_bound_to_exact_normalized_proposal(project, monkeypatch):
    _, sources = project
    value = proposal(sources)
    monkeypatch.setattr(trial, "_execute", lambda *args: pytest.fail("unconfirmed execution"))
    with pytest.raises(trial.TrialError) as error:
        trial.run_project_trial(sources, value, confirmed_digest="a" * 64)
    assert error.value.code == "project_confirmation_mismatch"


def test_snapshot_rechecks_every_file_before_copy(project, tmp_path):
    root, sources = project
    snapshot = sources.snapshot_manifest("examples:small")
    (root / "cases" / "search" / "build_solver.py").write_text("changed", encoding="utf-8")
    with pytest.raises(trial.TrialError) as error:
        trial._copy_snapshot(root, tmp_path / "copy", snapshot)
    assert error.value.code == "project_snapshot_changed"


def test_timeout_stays_failed_and_does_not_modify_source(project, monkeypatch, tmp_path):
    root, sources = project
    value = trial.validate_project_proposal(sources, proposal(sources))
    revision = sources.snapshot_manifest("examples:small")["source_digest"]
    monkeypatch.setattr(trial, "_execute", lambda *args: (1, "bounded trial timed out", True))
    result = trial.run_project_trial(sources, value, confirmed_digest=spec_digest(value), workspace_root=tmp_path / "jobs")
    assert result["status"] == "failed" and result["timed_out"] and not result["success"]
    assert result["error"]["code"] == "project_trial_timed_out"
    assert sources.snapshot_manifest("examples:small")["source_digest"] == revision
    assert not (root / ".blackbase").exists()


def test_service_time_limit_can_only_shorten_confirmed_budget(project, monkeypatch, tmp_path):
    _, sources = project
    value = trial.validate_project_proposal(sources, proposal(sources))
    observed = []
    def execute(_project, _run_id, _environment, timeout):
        observed.append(timeout)
        assert (_project / "results" / "exports").is_dir()
        assert (_project / "results" / "runtime").is_dir()
        return 1, "timeout", True
    monkeypatch.setattr(trial, "_execute", execute)
    result = trial.run_project_trial(sources, value, confirmed_digest=spec_digest(value),
                                    workspace_root=tmp_path / "jobs", timeout_seconds=10)
    assert observed == [10]
    assert result["status"] == "failed" and result["timed_out"]
    assert result["effective_timeout_seconds"] == 10


def test_runtime_data_reports_exact_source_files_and_effective_scalars(tmp_path):
    data = tmp_path / "input.csv"
    data.write_text("x,y\n1,2\n", encoding="utf-8")
    problem = SimpleNamespace(data=SimpleNamespace(input_path=data, rows=1))
    observed = trial._data_observation(problem, tmp_path)
    assert observed["scalars"] == {"rows": 1}
    assert observed["files"]["input_path"]["path"] == "input.csv"
    assert observed["files"]["input_path"]["sha256"] == hashlib.sha256(data.read_bytes()).hexdigest()
    problem.data.input_path = tmp_path.parent / "outside.csv"
    with pytest.raises(ValueError, match="escaped"):
        trial._data_observation(problem, tmp_path)


def test_real_project_trial_has_current_l0_raw_feedback_and_published_report(project, tmp_path):
    root, sources = project
    value = trial.validate_project_proposal(sources, proposal(sources))
    revision = sources.snapshot_manifest("examples:small")["source_digest"]
    result = trial.run_project_trial(sources, value, confirmed_digest=spec_digest(value), workspace_root=tmp_path / "jobs")
    assert result["status"] == "succeeded", result
    assert result["steps"] == 2
    assert result["evaluations"] >= 2
    assert result["resource_binding"]["current"] is True
    assert result["effective_problem"]["dimension"] == 2
    assert result["raw_results"]["raw_objectives"]
    assert result["project_result"]["publication"]["checksum"].startswith("sha256:")
    assert result["proposal_digest"] == spec_digest(value)
    assert result["project_id"] == "examples:small"
    assert sources.snapshot_manifest("examples:small")["source_digest"] == revision
    assert not (root / ".blackbase").exists()
    assert "DEEPSEEK_API_KEY" not in json.dumps(result)
    # The presentation copy cannot be changed into new "evidence" after the
    # authority published it.  Reuse this actual completed run to check that.
    copied_project = tmp_path / "jobs" / result["run_id"] / "project"
    report_path = copied_project / "results" / "project_trial_report.json"
    original = report_path.read_bytes()
    changed = json.loads(original)
    changed["initial"]["dimension"] = 999
    report_path.write_text(json.dumps(changed), encoding="utf-8")
    try:
        with pytest.raises(trial.TrialError) as error:
            trial._verified_results(copied_project, value, result["run_id"])
        assert error.value.code == "project_report_invalid"
    finally:
        report_path.write_bytes(original)


def test_download_archive_contains_only_bound_result_exports(tmp_path):
    exports = tmp_path / "results" / "exports"
    exports.mkdir(parents=True)
    data = b"day,quantity\n0,23\n"
    (exports / "plan.csv").write_bytes(data)
    (exports / "plan.audit.json").write_text('{"feasible":true}', encoding="utf-8")
    (exports / "credentials.json").write_text('{"password":"private-value"}', encoding="utf-8")
    (tmp_path / "results" / "project_trial_report.json").write_text("large raw report", encoding="utf-8")
    records = trial._result_file_manifest(tmp_path)
    archive, truncated = trial._artifact_archive(tmp_path, records, "trial-fixed")
    assert archive and truncated
    raw = base64.b64decode(archive["base64"])
    assert len(raw) == archive["size_bytes"] <= trial.MAX_ARTIFACT_ARCHIVE_BYTES
    assert hashlib.sha256(raw).hexdigest() == archive["sha256"]
    with ZipFile(io.BytesIO(raw)) as value:
        assert set(value.namelist()) == {"results/exports/plan.csv", "results/exports/plan.audit.json"}
        assert value.read("results/exports/plan.csv") == data
    assert len(records) == 3  # full declared manifest includes the omitted secret result
    assert "results/exports/credentials.json" in archive["omitted_files"]


def test_archive_detects_changed_or_escaping_result_bytes(tmp_path):
    exports = tmp_path / "results" / "exports"
    exports.mkdir(parents=True)
    path = exports / "plan.csv"
    path.write_text("a,b\n1,2\n", encoding="utf-8")
    records = trial._result_file_manifest(tmp_path)
    path.write_text("changed", encoding="utf-8")
    with pytest.raises(trial.TrialError) as error:
        trial._artifact_archive(tmp_path, records, "trial-fixed")
    assert error.value.code == "project_artifact_changed"
    with pytest.raises(trial.TrialError) as error:
        trial._safe_result_path(tmp_path, "results/../../outside.csv")
    assert error.value.code == "project_artifact_scope"


def test_archive_is_bounded_and_reports_omitted_files(tmp_path, monkeypatch):
    exports = tmp_path / "results" / "exports"
    exports.mkdir(parents=True)
    (exports / "a.csv").write_bytes(b"a,b\n1,2\n")
    (exports / "b.csv").write_bytes(os.urandom(12000))
    records = trial._result_file_manifest(tmp_path)
    monkeypatch.setattr(trial, "MAX_ARTIFACT_ARCHIVE_BYTES", 1024)
    archive, truncated = trial._artifact_archive(tmp_path, records, "trial-fixed")
    assert archive and truncated and archive["size_bytes"] <= 1024
    assert archive["included_files"] == ["results/exports/a.csv"]
    assert archive["omitted_files"] == ["results/exports/b.csv"]
    assert len(records) == 2


def test_archive_rejects_result_symlinks(tmp_path):
    exports = tmp_path / "results" / "exports"
    exports.mkdir(parents=True)
    outside = tmp_path / "outside.csv"
    outside.write_text("private", encoding="utf-8")
    try:
        (exports / "linked.csv").symlink_to(outside)
    except OSError:
        pytest.skip("symlink privilege is unavailable")
    with pytest.raises(trial.TrialError) as error:
        trial._result_file_manifest(tmp_path)
    assert error.value.code in {"project_artifact_link", "project_artifact_scope"}


def test_actual_production_parameter_contract_keeps_original_defaults():
    root = Path(__file__).resolve().parents[1]
    sources = ProjectSourceRegistry({"examples": root / "examples" / "cases"})
    schema = trial.project_parameter_schema(sources, "examples:production_scheduling", "production_scheduling")
    assert schema["properties"]["machines"]["default"] == 22
    assert schema["properties"]["materials"]["default"] == 156
    assert schema["properties"]["days"]["default"] == 31
    assert schema["properties"]["smoothness_penalty"]["default"] == 0.01
    assert schema["properties"]["smooth_strength"]["default"] == 0.6
    assert schema["properties"]["pop_size"]["requires_override"] is True
    assert "bom" not in schema["properties"] and "supply" not in schema["properties"]


@pytest.mark.parametrize("default,override", [(100000.0, 200000.0), (0.2, -250000.0)])
def test_float_scale_and_offset_are_not_execution_resource_sizes(project, default, override):
    root, sources = project
    path = root / "cases" / "search" / "build_solver.py"
    path.write_text(path.read_text().replace("default=0.2", f"default={default!r}"), encoding="utf-8")
    schema = trial.project_parameter_schema(sources, "examples:small", "search")
    rule = schema["properties"]["strength"]
    assert rule["default"] == default
    assert {"minimum", "maximum", "bounds_source", "requires_override"}.isdisjoint(rule)

    value = proposal(sources)
    value["parameters"] = {}
    assert trial.validate_project_proposal(sources, value)["parameters"] == {}
    value["parameters"] = {"strength": override}
    assert trial.validate_project_proposal(sources, value)["parameters"] == {"strength": override}

    from nsgablack.catalog.lab_workspace_parameters import parameter_form_plan, validate_parameter_overrides
    field = next(item for item in parameter_form_plan(schema)["fields"] if item["name"] == "strength")
    assert field["default_valid"] and not field["requires_override"]
    assert {"minimum", "maximum"}.isdisjoint(field)
    assert validate_parameter_overrides(schema, {"strength": override}) == {"strength": override}


@pytest.mark.parametrize("number", [float("nan"), float("inf"), -float("inf"), 10 ** 1000])
def test_unbounded_float_still_rejects_nonfinite_or_unrepresentable_values(project, number):
    _, sources = project
    value = proposal(sources)
    value["parameters"] = {"strength": number}
    with pytest.raises(trial.TrialError) as error:
        trial.validate_project_proposal(sources, value)
    assert error.value.code == "project_parameter_bounds"


@pytest.mark.parametrize("literal", ["1e309", "-1e309"])
def test_nonfinite_literal_default_requires_explicit_finite_override(project, literal):
    root, sources = project
    path = root / "cases" / "search" / "build_solver.py"
    path.write_text(path.read_text().replace("default=0.2", f"default={literal}"), encoding="utf-8")
    schema = trial.project_parameter_schema(sources, "examples:small", "search")
    rule = schema["properties"]["strength"]
    assert rule["requires_override"] and "default" not in rule
    assert "不是有限数值" in rule["description"]
    json.dumps(schema, allow_nan=False)
    value = proposal(sources)
    value["parameters"] = {}
    with pytest.raises(trial.TrialError) as error:
        trial.validate_project_proposal(sources, value)
    assert error.value.code == "project_parameter_override_required"
    value["parameters"] = {"strength": 100000.0}
    assert trial.validate_project_proposal(sources, value)["parameters"] == {"strength": 100000.0}

    from nsgablack.catalog.lab_workspace_parameters import parameter_form_plan, validate_parameter_overrides
    field = next(item for item in parameter_form_plan(schema)["fields"] if item["name"] == "strength")
    assert not field["has_default"] and field["requires_override"]
    with pytest.raises(ValueError, match="显式设置"):
        validate_parameter_overrides(schema, {})
    assert validate_parameter_overrides(schema, {"strength": 100000.0}) == {"strength": 100000.0}


@pytest.mark.parametrize("kind", ["int", "float"])
def test_count_parameters_keep_trial_cap_even_for_float_parser_declarations(project, kind):
    root, sources = project
    path = root / "cases" / "search" / "build_solver.py"
    path.write_text(path.read_text().replace('"--size", type=int, default=4',
        f'"--population-size", type={kind}, default=200'), encoding="utf-8")
    schema = trial.project_parameter_schema(sources, "examples:small", "search")
    rule = schema["properties"]["population_size"]
    assert rule["minimum"] == 0 and rule["maximum"] == 128
    assert rule["bounds_source"] == "trial_resource_policy" and rule["requires_override"]
    value = proposal(sources)
    value["parameters"] = {}
    with pytest.raises(trial.TrialError) as error:
        trial.validate_project_proposal(sources, value)
    assert error.value.code == "project_parameter_override_required"
    for count in (-1, 129):
        value["parameters"] = {"population_size": count}
        with pytest.raises(trial.TrialError) as error:
            trial.validate_project_proposal(sources, value)
        assert error.value.code == "project_parameter_bounds"
    value["parameters"] = {"population_size": 128}
    assert trial.validate_project_proposal(sources, value)["parameters"]["population_size"] == 128


@pytest.mark.parametrize("count", [-1, 10001])
def test_other_integer_parameters_keep_existing_conservative_trial_bounds(project, count):
    _, sources = project
    value = proposal(sources)
    value["parameters"] = {"size": count}
    with pytest.raises(trial.TrialError) as error:
        trial.validate_project_proposal(sources, value)
    assert error.value.code == "project_parameter_bounds"


def test_large_float_still_obeys_declared_numeric_choices(project):
    root, sources = project
    path = root / "cases" / "search" / "build_solver.py"
    path.write_text(path.read_text().replace('type=float, default=0.2',
        'type=float, default=100000.0, choices=[100000.0, 200000.0]'), encoding="utf-8")
    value = proposal(sources)
    value["parameters"] = {"strength": 300000.0}
    with pytest.raises(trial.TrialError) as error:
        trial.validate_project_proposal(sources, value)
    assert error.value.code == "project_parameter_choice"
    value["parameters"] = {"strength": 200000.0}
    assert trial.validate_project_proposal(sources, value)["parameters"]["strength"] == 200000.0


@pytest.mark.parametrize("explicit_scale", [False, True])
def test_production_directional_scale_passes_static_proposal_without_rewriting_case(explicit_scale):
    root = Path(__file__).resolve().parents[1]
    sources = ProjectSourceRegistry({"examples": root / "examples" / "cases"})
    schema = trial.project_parameter_schema(sources, "examples:production_scheduling", "production_scheduling")
    rule = schema["properties"]["objective_output_scale"]
    assert rule["default"] == 100000.0
    assert {"minimum", "maximum", "requires_override", "bounds_source"}.isdisjoint(rule)
    parameters = {"cooperation": "directional", "pop_size": 32, "moead_pop_size": 16,
                  "moead_neighborhood": 8, "vns_batch_size": 8, "quality_cycles": 1,
                  "explore_steps": 4, "refine_steps": 3, "refine_directions": 4,
                  "max_evaluations": 300}
    if explicit_scale:
        parameters["objective_output_scale"] = 100000.0
    value = {"schema": trial.PROPOSAL_SCHEMA, "project_id": "examples:production_scheduling",
             "project_revision": schema["project_revision"], "case_name": "production_scheduling",
             "parameters": parameters, "budget": {"max_steps": 32, "timeout_seconds": 180}, "seed": 42}
    checked = trial.validate_project_proposal(sources, value)
    assert checked["parameters"] == parameters
    assert checked["budget"] == {"max_steps": 32, "timeout_seconds": 180.0, "threads": 1, "gpus": 0}
