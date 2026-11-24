"""Real Project trials and fail-closed evidence/process boundaries."""
from __future__ import annotations

from contextlib import contextmanager
import json
import os
from pathlib import Path
import time

import psutil
import pytest

from nsgablack.catalog import lab_runner as runner
from nsgablack.catalog.lab_project import export_project, normalize_spec


@pytest.mark.parametrize("recipe", ["ga", "vns", "moead", "ga_vns"])
def test_real_trial_uses_project_l0_and_published_raw_results(recipe):
    spec = normalize_spec({"recipe": recipe})
    result = runner.run_trial(spec)
    assert result["status"] == "succeeded", result
    assert result["success"] is True
    assert result["error"] is None
    assert result["exit_code"] == 0
    assert 0 < result["steps"] <= spec["max_steps"]
    assert result["evaluations"] >= result["steps"]
    assert result["resource_binding"]["current"] is True
    assert result["project_result"]["case_name"] == "search"
    assert result["project_result"]["report_publication"]["checksum"].startswith("sha256:")
    assert result["results"]["refs"]
    assert result["pool"] and result["unit"]
    # All fields cross a JSON transport; no Path, provider session or ndarray.
    encoded = json.dumps(result, allow_nan=False)
    assert "nsgablack-lab-" not in encoded


@pytest.fixture(scope="module")
def completed_project(tmp_path_factory):
    root = tmp_path_factory.mktemp("lab-receipts")
    spec = normalize_spec({"recipe": "ga", "max_steps": 3})
    project = export_project(spec, root / "project")
    run_id = "lab-receipt-boundaries"
    code, logs, timed_out = runner._execute(project, run_id, runner._trial_environment(root), 60)
    assert code == 0 and not timed_out, logs
    runner._verify_receipts(project, spec, run_id)
    return project, spec, run_id


@contextmanager
def changed_json(path, change):
    original = path.read_bytes()
    value = json.loads(original)
    change(value)
    path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")
    try:
        yield
    finally:
        path.write_bytes(original)


def test_zero_exit_without_successful_project_manifest_is_rejected(completed_project):
    project, spec, run_id = completed_project
    path = project / ".blackbase" / "runs" / run_id / "manifest.json"
    with changed_json(path, lambda value: value.update(status="checked")):
        with pytest.raises(runner.TrialError, match="成功收据") as failure:
            runner._verify_receipts(project, spec, run_id)
    assert failure.value.code == "project_not_successful"


def test_case_must_confirm_actual_project_l0_binding(completed_project):
    project, spec, run_id = completed_project
    path = project / ".blackbase" / "runs" / run_id / "manifest.json"
    def remove_binding(value):
        value["cases"][0]["result"]["resource_usage"]["binding"]["current"] = False
    with changed_json(path, remove_binding):
        with pytest.raises(runner.TrialError) as failure:
            runner._verify_receipts(project, spec, run_id)
    assert failure.value.code == "resource_binding_not_current"


def test_report_copy_cannot_disagree_with_published_artifact(completed_project):
    project, spec, run_id = completed_project
    with changed_json(project / "results" / "lab_report.json",
                      lambda value: value.update(evaluations=999999)):
        with pytest.raises(runner.TrialError) as failure:
            runner._verify_receipts(project, spec, run_id)
    assert failure.value.code == "report_publication_invalid"


def test_result_without_publication_cannot_be_presented_as_success(completed_project):
    project, spec, run_id = completed_project
    path = project / ".blackbase" / "runs" / run_id / "manifest.json"
    def remove_publication(value):
        del value["cases"][0]["result"]["artifact_publications"]["lab_report"]
    with changed_json(path, remove_publication):
        with pytest.raises(runner.TrialError) as failure:
            runner._verify_receipts(project, spec, run_id)
    assert failure.value.code == "report_publication_missing"


def test_modified_artifact_fails_checksum_and_ledger_verification(completed_project):
    project, spec, run_id = completed_project
    path = project / ".blackbase" / "runs" / run_id / "manifest.json"
    manifest = json.loads(path.read_text(encoding="utf-8"))
    artifact = Path(manifest["cases"][0]["result"]["artifact_refs"]["lab_report"]["uri"])
    original = artifact.read_bytes()
    try:
        artifact.write_bytes(original + b" ")
        with pytest.raises(runner.TrialError) as failure:
            runner._verify_receipts(project, spec, run_id)
    finally:
        artifact.write_bytes(original)
    assert failure.value.code == "report_publication_invalid"


def test_old_run_identity_is_not_accepted(completed_project):
    project, spec, run_id = completed_project
    path = project / ".blackbase" / "runs" / run_id / "manifest.json"
    with changed_json(path, lambda value: value.update(run_id="another-run")):
        with pytest.raises(runner.TrialError) as failure:
            runner._verify_receipts(project, spec, run_id)
    assert failure.value.code == "project_not_successful"


def test_runtime_env_never_inherits_service_keys_database_or_resource_grants(monkeypatch, tmp_path):
    forbidden = ("DEEPSEEK_API_KEY", "OPENAI_API_KEY", "MYSQL_PASSWORD", "NSGABLACK_CATALOG_DB_CONFIG",
                 "NSGABLACK_RESOURCE_CONTEXT_JSON", "AWS_ACCESS_KEY_ID", "PYTHONSTARTUP")
    for key in forbidden:
        monkeypatch.setenv(key, "test-secret-that-must-not-be-inherited")
    monkeypatch.setenv("PYTHONPATH", "untrusted-parent-path")
    environment = runner._trial_environment(tmp_path)
    assert all(key not in environment for key in forbidden)
    assert "untrusted-parent-path" not in environment["PYTHONPATH"]
    assert environment["HOME"] == str(tmp_path)
    assert environment["OMP_NUM_THREADS"] == "1"


@pytest.mark.parametrize("spec", [{"command": "ignored"}, {"source": "print('x')"},
    {"recipe": "../outside"}, {"recipe": "ga", "max_steps": 100000}])
def test_commands_code_paths_and_unbounded_spec_are_not_executable(spec):
    result = runner.run_trial(spec)
    assert result["status"] == "failed"
    assert result["error"]["code"] == "spec_invalid"
    assert result["exit_code"] is None


@pytest.mark.parametrize("timeout", [True, 0, 91, float("nan"), "60"])
def test_unbounded_or_invalid_timeout_is_rejected(timeout):
    result = runner.run_trial({"recipe": "ga"}, timeout_seconds=timeout)
    assert result["error"]["code"] == "timeout_invalid"


def test_timeout_kills_project_and_child_process(tmp_path):
    (tmp_path / "run_project.py").write_text(
        "import subprocess,sys,time\n"
        "child=subprocess.Popen([sys.executable,'-c','import time;time.sleep(120)'])\n"
        "print(child.pid,flush=True)\n"
        "time.sleep(120)\n", encoding="utf-8")
    code, logs, timed_out = runner._execute(tmp_path, "fixed-test-run", runner._trial_environment(tmp_path), 1)
    assert timed_out and code != 0
    child_pid = int(logs.strip())
    deadline = time.monotonic() + 3
    while psutil.pid_exists(child_pid) and time.monotonic() < deadline:
        if psutil.Process(child_pid).status() == psutil.STATUS_ZOMBIE:
            break
        time.sleep(.02)
    assert not psutil.pid_exists(child_pid) or psutil.Process(child_pid).status() == psutil.STATUS_ZOMBIE


def test_excessive_logs_are_consumed_without_unbounded_storage(tmp_path):
    (tmp_path / "run_project.py").write_text(
        f"print('a'*{runner.MAX_LOG_BYTES * 4})\nprint('final marker')\n", encoding="utf-8")
    code, logs, timed_out = runner._execute(tmp_path, "fixed-test-run", runner._trial_environment(tmp_path), 5)
    assert code == 0 and not timed_out
    assert logs.endswith("final marker\n")
    assert len(logs.encode("utf-8")) <= runner.MAX_LOG_BYTES + 100
    assert logs.startswith("[较早日志已截断]")


def test_raw_selection_scores_cannot_replace_original_problem_values():
    ref = {"pool_id": "pool", "record_id": "version", "row": 0, "candidate_token": "token"}
    result = {"refs": [ref], "candidates": [[0., 0.]], "raw_objectives": [[0.]], "raw_violations": [0.]}
    with pytest.raises(runner.TrialError):
        runner._verify_candidates(result, normalize_spec({"recipe": "moead"}))
    result["raw_objectives"] = [[9., 9.]]
    with pytest.raises(runner.TrialError) as failure:
        runner._verify_candidates(result, normalize_spec({"recipe": "ga"}))
    assert failure.value.code == "raw_evaluation_mismatch"


def _custom_problem_spec():
    from nsgablack.catalog.lab_assembly import normalize_assembly
    return normalize_assembly({"problem": {"component": "problem.expression", "parameters": {
        "variables": [{"name": "amount", "low": 0, "high": 10}],
        "objectives": [{"name": "利润", "expression": "8*amount-amount**2", "direction": "max"}],
        "constraints": [{"name": "限额", "expression": "amount", "relation": "<=", "rhs": 6}]}},
        "initial_count": 8, "max_steps": 3,
        "nodes": [{"id": "ga", "component": "adapter.nsga2", "parameters": {"population_size": 4, "offspring_size": 4}}],
        "plan": {"kind": "stage", "node": "ga", "steps": 3}})


def test_custom_problem_verifier_preserves_max_direction_and_nonzero_hard_violation():
    spec = _custom_problem_spec()
    ref = {"pool_id": "pool", "record_id": "version", "row": 0, "candidate_token": "token"}
    result = {"refs": [ref], "candidates": [[7.]], "raw_objectives": [[-7.]], "raw_violations": [1.]}
    runner._verify_candidates(result, spec)
    result["raw_violations"] = [0.]
    with pytest.raises(runner.TrialError, match="原始目标或约束"):
        runner._verify_candidates(result, spec)
    result.update(raw_violations=[1.], raw_objectives=[[7.]])
    with pytest.raises(runner.TrialError):
        runner._verify_candidates(result, spec)


def test_real_custom_problem_trial_delivers_human_values_without_rewriting_raw():
    result = runner.run_trial(_custom_problem_spec())
    assert result["status"] == "succeeded", result["logs"][-3000:]
    values = result["results"]
    assert values["objective_names"] == ["利润"] and values["objective_directions"] == ["max"]
    assert values["variable_names"] == ["amount"]
    for point, raw, shown, violation in zip(values["candidates"], values["raw_objectives"],
                                            values["display_objectives"], values["raw_violations"]):
        expected = 8 * point[0] - point[0] ** 2
        assert shown[0] == pytest.approx(expected) and raw[0] == pytest.approx(-expected)
        assert violation == pytest.approx(max(point[0] - 6, 0))
    assert all("best_feasible_raw_sum" in record and "feasible_count" in record for record in result["records"])
