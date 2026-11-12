"""Frozen code revisions, real Project receipts and persistent local jobs."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil
import threading
import time
from uuid import uuid4

import pytest

from nsgablack.catalog import lab_workspace_runner as execution
from nsgablack.catalog.lab_jobs import spec_digest
from nsgablack.catalog.lab_project_sources import ProjectSourceRegistry
from nsgablack.catalog.lab_project_trial import (TrialError, project_parameter_schema,
    run_project_trial, validate_project_proposal)
from nsgablack.catalog.lab_workspace_store import WorkspaceError, WorkspaceStore


@pytest.fixture
def workspace(tmp_path):
    source = Path(__file__).resolve().parents[1] / "examples" / "cases" / "catalog_fixed_candidate"
    original = tmp_path / "examples" / "fixed"
    shutil.copytree(source, original, ignore=shutil.ignore_patterns(
        "__pycache__", "results", ".blackbase", ".pytest_cache", "run_logs", "runs"))
    sources = ProjectSourceRegistry({"examples": original.parent})
    store = WorkspaceStore(tmp_path / "workspaces", sources)
    item = store.create_workspace("examples:fixed", title="Fixed candidate editing")
    runner = execution.WorkspaceRunner(store)
    yield original, sources, store, item, runner
    runner.close()


def _wait(runner, workspace_id, job_id):
    deadline = time.monotonic() + 75
    while time.monotonic() < deadline:
        item = runner.get_job(workspace_id, job_id)
        if item["status"] not in {"queued", "running"}:
            return item
        time.sleep(.02)
    pytest.fail("bounded local Project job did not finish")


def _proposal(sources):
    return {"schema": "nsgablack.project_trial/v1", "project_id": "examples:fixed",
        "project_revision": sources.snapshot_manifest("examples:fixed")["source_digest"],
        "case_name": "fixed", "parameters": {},
        "budget": {"max_steps": 1, "timeout_seconds": 60, "threads": 1, "gpus": 0}, "seed": 42}


def test_parameterless_project_requires_the_explicit_local_mode(workspace):
    _, sources, _, _, _ = workspace
    value = _proposal(sources)
    with pytest.raises(TrialError, match="参数契约"):
        project_parameter_schema(sources, "examples:fixed", "fixed")
    with pytest.raises(TrialError):
        validate_project_proposal(sources, value)
    with pytest.raises(TrialError):
        run_project_trial(sources, value, confirmed_digest=spec_digest(value))
    schema = project_parameter_schema(sources, "examples:fixed", "fixed", allow_parameterless=True)
    assert schema["parameter_mode"] == "none" and schema["properties"] == {}
    assert validate_project_proposal(sources, value, allow_parameterless=True)["parameters"] == {}
    with pytest.raises(TrialError) as error:
        validate_project_proposal(sources, {**value, "parameters": {"invented": 3}}, allow_parameterless=True)
    assert error.value.code == "project_parameter_unknown"
    with pytest.raises(TrialError) as error:
        project_parameter_schema(sources, "examples:fixed", "fixed", allow_parameterless="yes")
    assert error.value.code == "invalid_parameter_mode"


def test_static_check_does_not_import_builder_or_construct_unit(workspace, monkeypatch):
    _, _, store, item, runner = workspace
    wid, rid = item["workspace_id"], item["head_revision"]
    path = "cases/fixed/build_solver.py"
    contents = store.read_file(wid, rid, path)["content"]
    revision = store.save_files(wid, {path: "raise RuntimeError('must not import')\n" + contents}, expected_revision=rid)
    monkeypatch.setattr(execution, "run_project_trial", lambda *a, **k: pytest.fail("static check executed a trial"))
    from nsgablack.units import UnitBinding
    monkeypatch.setattr(UnitBinding, "build", lambda *a, **k: pytest.fail("static check created Unit"))
    checked = runner.check(wid, revision["revision_id"], "fixed", max_steps=1)
    assert checked["ok"] and not checked["builder_executed"] and not checked["algorithm_executed"]
    assert checked["scope"] == "frozen_revision_static_only"
    assert checked["parameter_schema"]["parameter_mode"] == "none"
    assert runner.list_jobs(wid) == []


@pytest.mark.parametrize("parameters", [{}, {"comparison_scale": 100000.0}])
def test_static_workspace_check_accepts_algorithm_scale_without_a_resource_override(workspace, monkeypatch, parameters):
    _, _, store, item, runner = workspace
    wid, rid = item["workspace_id"], item["head_revision"]
    path = "cases/fixed/build_solver.py"
    contents = store.read_file(wid, rid, path)["content"]
    declaration = '''
import argparse
def build_parser():
    parser = argparse.ArgumentParser()
    parser.add_argument("--comparison-scale", type=float, default=100000.0)
    return parser
'''
    revision = store.save_files(wid, {path: "raise RuntimeError('must not import')\n" + contents + declaration},
                                expected_revision=rid)
    monkeypatch.setattr(execution, "run_project_trial", lambda *a, **k: pytest.fail("static check executed a trial"))
    checked = runner.check(wid, revision["revision_id"], "fixed", parameters=parameters, max_steps=1)
    assert checked["ok"], checked["diagnostics"]
    assert checked["proposal"]["parameters"] == parameters
    assert not checked["builder_executed"] and not checked["algorithm_executed"]
    assert runner.list_jobs(wid) == []


def test_syntax_draft_is_saved_but_cannot_be_submitted(workspace, monkeypatch):
    _, _, store, item, runner = workspace
    wid, rid = item["workspace_id"], item["head_revision"]
    revision = store.save_files(wid, {"cases/fixed/problem/__init__.py": "def broken(:\n"}, expected_revision=rid)
    monkeypatch.setattr(execution, "run_project_trial", lambda *a, **k: pytest.fail("invalid source ran"))
    checked = runner.check(wid, revision["revision_id"], "fixed")
    assert not checked["ok"]
    diagnostic = next(x for x in checked["diagnostics"] if x["code"] == "workspace_python_syntax")
    assert diagnostic["line"] == 1 and diagnostic["path"] == "cases/fixed/problem/__init__.py"
    with pytest.raises(WorkspaceError) as error:
        runner.submit(wid, revision["revision_id"], "fixed", request_id=uuid4().hex)
    assert error.value.code == "workspace_static_check_failed"
    assert runner.list_jobs(wid) == []


def test_request_is_durable_and_shared_without_duplicate_execution(workspace, monkeypatch):
    _, _, store, item, runner = workspace
    wid, rid = item["workspace_id"], item["head_revision"]
    entered, release = threading.Event(), threading.Event()
    calls = []
    def run(*args, **kwargs):
        calls.append(args[1]["project_revision"])
        entered.set()
        assert release.wait(10)
        return {"success": True, "run_id": "one-local-run", "error": None}
    monkeypatch.setattr(execution, "run_project_trial", run)
    request = uuid4().hex
    first = runner.submit(wid, rid, "fixed", request_id=request)
    assert entered.wait(10)
    second_runner = execution.WorkspaceRunner(WorkspaceStore(store.root, store.sources))
    try:
        duplicate = second_runner.submit(wid, rid, "fixed", request_id=request)
        assert duplicate["job_id"] == first["job_id"]
        assert duplicate["status"] == "running"
        with pytest.raises(WorkspaceError) as error:
            second_runner.submit(wid, rid, "fixed", max_steps=3, request_id=request)
        assert error.value.code == "workspace_request_conflict"
    finally:
        release.set()
    done = _wait(runner, wid, first["job_id"])
    assert done["status"] == "succeeded" and len(calls) == 1
    runner.close()
    fresh = execution.WorkspaceRunner(WorkspaceStore(store.root, store.sources))
    assert fresh.get_job(wid, first["job_id"])["result"]["run_id"] == "one-local-run"
    assert fresh.submit(wid, rid, "fixed", request_id=request)["job_id"] == first["job_id"]
    assert len(calls) == 1
    fresh.close()


def test_failed_result_and_exact_revision_remain_in_history(workspace, monkeypatch):
    _, _, store, item, runner = workspace
    wid, rid = item["workspace_id"], item["head_revision"]
    monkeypatch.setattr(execution, "run_project_trial", lambda *a, **k: {
        "success": False, "run_id": "failed-local-run", "error": {"code": "problem_failed", "message": "evaluation failed"}})
    job = runner.submit(wid, rid, "fixed", request_id=uuid4().hex)
    done = _wait(runner, wid, job["job_id"])
    assert done["status"] == "failed" and done["error"]["code"] == "problem_failed"
    assert done["revision_id"] == rid and done["finished_at"] >= done["created_at"]
    other = store.create_workspace("examples:fixed")
    with pytest.raises(WorkspaceError) as error:
        runner.get_job(other["workspace_id"], job["job_id"])
    assert error.value.code == "workspace_job_missing"
    runner.close()
    restarted = execution.WorkspaceRunner(store)
    assert restarted.list_jobs(wid)[0]["result"]["run_id"] == "failed-local-run"
    restarted.close()


def test_crashed_owner_is_interrupted_without_automatic_retry(workspace, monkeypatch):
    _, _, _, item, runner = workspace
    wid, rid = item["workspace_id"], item["head_revision"]
    job_id = uuid4().hex
    record = {"job_id": job_id, "workspace_id": wid, "revision_id": rid,
        "case_name": "fixed", "request_id": uuid4().hex, "fingerprint": "f" * 64,
        "status": "running", "created_at": time.time(), "started_at": time.time(),
        "finished_at": None, "result": None, "error": None}
    with runner._db.connect() as db:
        db.execute("INSERT INTO workspace_jobs VALUES (?,?,?,?,?,?,?)", (
            job_id, wid, record["request_id"], record["fingerprint"], "running", record["created_at"], json.dumps(record)))
        db.execute("INSERT OR REPLACE INTO workspace_runner_owner VALUES(1,?)", (
            json.dumps({"id": uuid4().hex, "pid": 2147483647, "process_created": 0}),))
    monkeypatch.setattr(execution, "run_project_trial", lambda *a, **k: pytest.fail("restart retried a problem"))
    restarted = execution.WorkspaceRunner(runner.store)
    done = restarted.get_job(wid, job_id)
    assert done["status"] == "interrupted" and done["result"] is None
    assert done["error"]["code"] == "workspace_runner_interrupted"
    assert restarted.list_jobs(wid)[0]["job_id"] == job_id
    restarted.close()


def test_registry_filtering_cannot_change_frozen_revision_silently(workspace, monkeypatch):
    _, _, store, item, runner = workspace
    wid, rid = item["workspace_id"], item["head_revision"]
    get = store.get_revision
    monkeypatch.setattr(store, "get_revision", lambda *a, **k: {**get(*a, **k), "source_digest": "0" * 64})
    checked = runner.check(wid, rid, "fixed")
    assert not checked["ok"] and checked["diagnostics"][0]["code"] == "workspace_revision_mismatch"
    with pytest.raises(WorkspaceError):
        runner.submit(wid, rid, "fixed", request_id=uuid4().hex)


def test_real_project_receipts_bind_both_problem_revisions(workspace):
    original, sources, store, item, runner = workspace
    wid, initial = item["workspace_id"], item["head_revision"]
    original_digest = sources.snapshot_manifest("examples:fixed")["source_digest"]
    first = runner.submit(wid, initial, "fixed", max_steps=1, request_id=uuid4().hex)
    path = "cases/fixed/problem/__init__.py"
    contents = store.read_file(wid, initial, path)["content"]
    changed = contents.replace("return float(np.sum(np.asarray(x, dtype=float) ** 2))",
                               "return float(np.sum(np.asarray(x, dtype=float) ** 2)) + 1.0")
    assert changed != contents
    second_revision = store.save_files(wid, {path: changed}, expected_revision=initial, message="add one to raw objective")
    second = runner.submit(wid, second_revision["revision_id"], "fixed", max_steps=1, request_id=uuid4().hex)
    before = _wait(runner, wid, first["job_id"])
    after = _wait(runner, wid, second["job_id"])
    assert before["status"] == after["status"] == "succeeded", [before, after]
    for job in (before, after):
        result = job["result"]
        assert result["resource_binding"]["current"] is True
        assert result["steps"] == 1 and result["evaluations"] == 1
        assert result["project_revision"] == job["source_digest"]
        assert result["project_result"]["case_status"] == "succeeded"
    assert before["revision_id"] == initial
    assert after["revision_id"] == second_revision["revision_id"]
    assert before["source_digest"] != after["source_digest"]
    assert before["result"]["run_id"] != after["result"]["run_id"]
    # ProjectTrialReport emits aligned raw rows without applying another Bias.
    assert before["result"]["raw_results"]["raw_objectives"] == [[.625]]
    assert after["result"]["raw_results"]["raw_objectives"] == [[1.625]]
    assert sources.snapshot_manifest("examples:fixed")["source_digest"] == original_digest
    assert (original / path).read_text(encoding="utf-8") == contents
    runner.close()
    restarted = execution.WorkspaceRunner(WorkspaceStore(store.root, sources))
    assert {j["job_id"] for j in restarted.list_jobs(wid)} == {first["job_id"], second["job_id"]}
    assert restarted.get_job(wid, first["job_id"])["result"]["raw_results"]["raw_objectives"] == [[.625]]
    restarted.close()
