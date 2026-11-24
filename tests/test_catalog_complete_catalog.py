"""Explicit completion job uses fake probes/workers, never paid providers."""
import hashlib
import importlib.util
import json
from pathlib import Path

import pytest


@pytest.fixture
def driver():
    path = Path(__file__).resolve().parents[1] / "deployment/catalog/complete_catalog.py"
    spec = importlib.util.spec_from_file_location("completion_driver_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def packets(count=3):
    entries = [{"key": f"adapter.item_{i:03}", "digest": f"{i:064x}",
                "cached": False, "evidence": True} for i in range(count)]
    return {"model": "deepseek-flash", "prompt": "catalog-tutorial-reviewed-zh-v11", "entries": entries,
            "source_index_sha256": hashlib.sha256(json.dumps(
                {item["key"]: item["digest"] for item in entries}, sort_keys=True,
                separators=(",", ":")).encode()).hexdigest()}


class FakeDocker:
    def __init__(self, count=3):
        self.probe = packets(count)
        self.probes = 0
        self.image_id = "sha256:" + "a" * 64

    def image(self):
        return self.image_id, "frozen-release"

    def run(self, image, *, probe):
        assert probe is True  # The driver cannot use the old writer quota path.
        self.probes += 1
        return json.loads(json.dumps(self.probe))


def ordinary(driver, root, *, reserved=657, catchup=557):
    path = root / "automation/state/state.json"
    driver.write_json(path, {"schema": "nsgablack.catalog.auto_curate/v1", "budget_day": "2026-10-26",
                            "reserved": reserved, "catchup_reserved": catchup, "cursor": "",
                            "failures": {}, "circuit_until": 0})
    return path, path.read_bytes()


def ledger(root, job="all557"):
    return root / "automation/state/completions" / job / "job.json"


def execute(driver, root, docker, worker, *, now=100000, **kwargs):
    options = {"execute": True, "max_batches": driver.TOTAL * driver.MAX_ATTEMPTS, **kwargs}
    return driver.run_job(root, job_id="all557", docker=docker, worker=worker,
                          expected_total=len(docker.probe["entries"]), now=now, **options)


def success_worker(docker):
    def run(image, *, keys, feedback, report_dir, job_id, batch_id):
        for item in docker.probe["entries"]:
            if item["key"] in keys:
                item["cached"] = True
        return {"results": [{"entry_key": key} for key in keys]}
    return run


def test_all_557_are_completed_with_exact_store_confirmation_and_no_old_quota_reset(driver, tmp_path):
    path, before = ordinary(driver, tmp_path)
    docker = FakeDocker(557)
    docker.probe["entries"][0]["cached"] = True
    calls = []
    good = success_worker(docker)
    def worker(image, **kwargs):
        saved = json.loads(ledger(tmp_path).read_text())
        assert all(saved["targets"][key]["status"] == "reserved" for key in kwargs["keys"])
        assert saved["reserved"] == sum(item["attempts"] for item in saved["targets"].values())
        calls.extend(kwargs["keys"])
        return good(image, **kwargs)
    result = execute(driver, tmp_path, docker, worker)
    assert result["complete"] and result["current"] == result["total"] == 557
    assert result["remaining"] == 0 and result["reserved"] == 556
    assert len(calls) == len(set(calls)) == 556 and "adapter.item_000" not in calls
    assert path.read_bytes() == before
    saved = json.loads(ledger(tmp_path).read_text())
    assert saved["ordinary_at_start"]["reserved"] == 657
    assert saved["ordinary_at_start"]["catchup_reserved"] == 557
    assert all((ledger(tmp_path).parent / batch["report_ref"]).exists() for batch in saved["batches"])
    assert docker.probes >= 3  # Includes the independent final confirmation.


def test_reported_success_without_store_visibility_never_completes(driver, tmp_path):
    docker = FakeDocker()
    result = execute(driver, tmp_path, docker, lambda image, **kw: {"results": [{"entry_key": k} for k in kw["keys"]]})
    assert not result["complete"] and result["current"] == 0 and result["status"] == "backoff"
    assert result["next_eligible_at"] == 100900
    saved = json.loads(ledger(tmp_path).read_text())
    assert all(item["last_failure"] == {"error": "store_not_visible"} for item in saved["targets"].values())


def test_real_rejection_feedback_survives_restart_and_is_forwarded_only_on_retry(driver, tmp_path):
    docker = FakeDocker(1)
    failure = {"entry_key": "adapter.item_000", "error": "note_evidence_validation_failed",
               "validation_issue": "Tutorial source review did not approve publication",
               "source_review": {"decision": "revise", "issues": [{"location": "extensions[0]",
                   "problem": "Callback is not installed", "required_change": "Wire the callback in the actual builder",
                   "evidence_ids": ["e1"]}], "checks": ["Checked the builder"], "evidence_ids": ["e1"], "version": "review-v5"}}
    calls = []
    def reject(image, **kw):
        calls.append(kw["feedback"])
        return {"results": [failure]}
    first = execute(driver, tmp_path, docker, reject)
    assert first["status"] == "backoff" and calls == [{}]
    assert execute(driver, tmp_path, docker, reject, now=100899)["status"] == "backoff"
    assert len(calls) == 1
    def approve(image, **kw):
        previous = kw["feedback"]["adapter.item_000"]
        assert previous["validation_issue"] == failure["validation_issue"]
        assert previous["source_review"] == failure["source_review"]
        return success_worker(docker)(image, **kw)
    assert execute(driver, tmp_path, docker, approve, now=100900)["complete"]
    saved = json.loads(ledger(tmp_path).read_text())
    assert saved["reserved"] == 2 and saved["round"] == 2
    assert len(saved["batches"]) == 2


def test_each_identity_max_three_durable_attempts_even_across_restarts(driver, tmp_path):
    docker = FakeDocker(1)
    calls = []
    def fail(image, **kw):
        calls.append(kw)
        return {"results": [{"entry_key": kw["keys"][0], "error": "ai_transport_failed"}]}
    for moment in (100000, 100900, 102700):
        result = execute(driver, tmp_path, docker, fail, now=moment)
    assert result["status"] == "attempt_limit" and result["reserved"] == 3
    assert execute(driver, tmp_path, docker, fail, now=999999)["status"] == "attempt_limit"
    assert len(calls) == 3


def test_no_evidence_is_explicit_incomplete_and_does_not_block_other_keys(driver, tmp_path):
    docker = FakeDocker()
    docker.probe["entries"][0]["evidence"] = False
    result = execute(driver, tmp_path, docker, success_worker(docker))
    assert result["status"] == "awaiting_evidence" and not result["complete"]
    assert result["current"] == 2 and result["reserved"] == 2


@pytest.mark.parametrize("code", [401, 402, 403])
def test_authentication_failure_stops_remaining_batches_with_durable_reason(driver, tmp_path, code):
    docker, calls = FakeDocker(23), []
    def worker(image, **kw):
        calls.append(kw["keys"])
        return {"results": [{"entry_key": key, "error": f"ai_http_{code}"} for key in kw["keys"]]}
    result = execute(driver, tmp_path, docker, worker)
    assert result["status"] == "auth_blocked" and result["next_eligible_at"] == 186400
    assert len(calls) == 1 and result["reserved"] == 20
    assert execute(driver, tmp_path, docker, worker, now=100001)["status"] == "auth_blocked"
    assert len(calls) == 1


def test_existing_backoff_and_circuit_are_respected_without_touching_timer_state(driver, tmp_path):
    path, _ = ordinary(driver, tmp_path)
    docker = FakeDocker(1)
    state = json.loads(path.read_text())
    auto = driver.sibling("auto_curate")
    state["failures"][auto.identity(docker.probe["entries"][0], docker.probe)] = {"count": 5, "next": 100901}
    driver.write_json(path, state)
    before = path.read_bytes()
    def forbidden(*args, **kwargs):
        raise AssertionError("Backed off entry must not be sent")
    result = execute(driver, tmp_path, docker, forbidden)
    assert result["status"] == "backoff" and result["reserved"] == 0
    assert path.read_bytes() == before


def test_crash_keeps_reservation_and_resume_records_unknown_outcome(driver, tmp_path):
    docker = FakeDocker(1)
    def crash(image, **kw):
        assert json.loads(ledger(tmp_path).read_text())["reserved"] == 1
        raise KeyboardInterrupt()
    with pytest.raises(KeyboardInterrupt):
        execute(driver, tmp_path, docker, crash)
    saved = json.loads(ledger(tmp_path).read_text())
    assert saved["reserved"] == 1 and saved["targets"]["adapter.item_000"]["status"] == "outcome_unknown"
    assert (ledger(tmp_path).parent / saved["batches"][0]["report_ref"]).exists()
    result = execute(driver, tmp_path, docker, success_worker(docker), now=100001)
    assert result["reserved"] == 1 and result["status"] == "backoff"
    saved = json.loads(ledger(tmp_path).read_text())
    assert saved["targets"]["adapter.item_000"]["last_failure"] == {"error": "worker_interrupted"}


@pytest.mark.parametrize("change", ["image", "model", "prompt", "source"])
def test_identity_change_stops_before_any_retry(driver, tmp_path, change):
    docker = FakeDocker(1)
    execute(driver, tmp_path, docker, lambda image, **kw: {"results": []})
    if change == "image":
        docker.image_id = "sha256:" + "b" * 64
    elif change in {"model", "prompt"}:
        docker.probe[change] += "-changed"
    else:
        docker.probe["entries"][0]["digest"] = "f" * 64
        docker.probe["source_index_sha256"] = hashlib.sha256(json.dumps(
            {item["key"]: item["digest"] for item in docker.probe["entries"]}, sort_keys=True,
            separators=(",", ":")).encode()).hexdigest()
    with pytest.raises(driver.CompletionError, match="identity_changed"):
        execute(driver, tmp_path, docker, success_worker(docker), now=100900)
    assert json.loads(ledger(tmp_path).read_text())["reserved"] == 1


def test_safe_reports_do_not_persist_unknown_fields_provider_bodies_or_secrets(driver, tmp_path):
    docker = FakeDocker(1)
    secret = "sk-" + "unsafecredential" * 4
    def worker(image, **kw):
        return {"raw": secret, "results": [{"entry_key": kw["keys"][0], "error": "ai_response_incomplete",
            "provider_phase": "review", "validation_issue": "api_key=" + secret,
            "headers": {"Authorization": secret}, "content": secret,
            "provider_diagnostics": {"finish_reason": "length", "completion_tokens": 12288,
                                     "raw_content": secret, "api_key": secret}}]}
    result = execute(driver, tmp_path, docker, worker)
    text = "\n".join(path.read_text(encoding="utf-8") for path in ledger(tmp_path).parent.rglob("*.json"))
    assert secret not in text and "Authorization" not in text and "raw_content" not in text
    assert '"completion_tokens":12288' in text and '"provider_phase":"review"' in text
    assert not result["complete"]


def test_guard_rechecks_store_before_paid_call(driver, tmp_path):
    docker = FakeDocker(1)
    original = docker.run
    def probe(image, *, probe):
        if docker.probes == 1:
            docker.probe["entries"][0]["cached"] = True
        return original(image, probe=probe)
    docker.run = probe
    def forbidden(*args, **kwargs):
        raise AssertionError("Newly current key must not be sent")
    result = execute(driver, tmp_path, docker, forbidden)
    assert result["complete"] and result["reserved"] == 0


def test_complete_requires_second_fresh_confirmation_and_exact_expected_total(driver, tmp_path):
    docker = FakeDocker(1)
    docker.probe["entries"][0]["cached"] = True
    assert execute(driver, tmp_path, docker, success_worker(docker))["complete"]
    assert docker.probes == 2
    with pytest.raises(driver.CompletionError, match="catalog_total_mismatch"):
        driver.run_job(tmp_path, job_id="wrongtotal", docker=docker, worker=success_worker(docker), execute=True)


def test_malformed_duplicate_report_is_diagnosed_without_forging_progress(driver, tmp_path):
    docker = FakeDocker(1)
    result = execute(driver, tmp_path, docker, lambda image, **kw: {"results": [
        {"entry_key": kw["keys"][0]}, {"entry_key": kw["keys"][0]}]})
    assert not result["complete"] and result["reserved"] == 1
    saved = json.loads(ledger(tmp_path).read_text())
    assert saved["targets"]["adapter.item_000"]["last_failure"] == {"error": "batch_report_invalid"}


def test_retry_feedback_must_match_frozen_source_identity(driver, tmp_path):
    docker = FakeDocker(1)
    execute(driver, tmp_path, docker, lambda image, **kw: {"results": [
        {"entry_key": kw["keys"][0], "error": "note_evidence_validation_failed",
         "validation_issue": "Usage API contract mismatch: target/unknown keyword/expected params"}]})
    saved = json.loads(ledger(tmp_path).read_text())
    path = ledger(tmp_path).parent / saved["batches"][0]["report_ref"]
    report = json.loads(path.read_text())
    report["identity"]["source_index_sha256"] = "f" * 64
    driver.write_json(path, report)
    with pytest.raises(driver.CompletionError, match="feedback_identity_mismatch"):
        execute(driver, tmp_path, docker, success_worker(docker), now=100900)
    saved = json.loads(ledger(tmp_path).read_text())
    assert saved["reserved"] == 1
    assert saved["last_status"]["status"] == "feedback_identity_mismatch"


def test_one_failed_identity_does_not_block_remaining_first_round(driver, tmp_path):
    docker = FakeDocker(23)
    calls = []
    good = success_worker(docker)
    def worker(image, **kw):
        saved = json.loads(ledger(tmp_path).read_text())
        calls.append((saved["round"], list(kw["keys"])))
        if "adapter.item_000" in kw["keys"]:
            rest = {**kw, "keys": [key for key in kw["keys"] if key != "adapter.item_000"]}
            rows = good(image, **rest)["results"]
            return {"results": [{"entry_key": "adapter.item_000", "error": "ai_transport_failed"}, *rows]}
        return good(image, **kw)
    result = execute(driver, tmp_path, docker, worker)
    assert result["status"] == "backoff" and result["current"] == 22
    assert [len(keys) for _, keys in calls] == [20, 3]
    assert all(number == 1 for number, _ in calls)
    assert sum("adapter.item_000" in keys for _, keys in calls) == 1


def test_source_change_during_batch_keeps_report_but_never_runs_next_batch(driver, tmp_path):
    docker = FakeDocker(23)
    calls = []
    def worker(image, **kw):
        calls.append(kw["keys"])
        result = success_worker(docker)(image, **kw)
        docker.image_id = "sha256:" + "b" * 64
        return result
    with pytest.raises(driver.CompletionError, match="identity_changed"):
        execute(driver, tmp_path, docker, worker)
    saved = json.loads(ledger(tmp_path).read_text())
    assert len(calls) == 1 and saved["reserved"] == 20
    assert saved["last_status"]["status"] == "identity_changed"
    assert (ledger(tmp_path).parent / saved["batches"][0]["report_ref"]).exists()


def test_cli_uses_same_nonblocking_worker_lock_and_partial_is_nonzero(driver, tmp_path, monkeypatch, capsys):
    import sys
    import types
    monkeypatch.setattr(driver.os, "geteuid", lambda: 0, raising=False)
    calls = []
    monkeypatch.setitem(sys.modules, "fcntl", types.SimpleNamespace(
        LOCK_EX=2, LOCK_NB=4, flock=lambda descriptor, flags: calls.append(flags)))
    monkeypatch.setattr(driver, "run_job", lambda *a, **kw: {"complete": False, "status": "attempt_limit"})
    assert driver.main(["--root", str(tmp_path), "--job-id", "all557", "--execute"]) == 2
    assert calls == [6] and (tmp_path / "automation/state/worker.lock").exists()
    assert '"complete": false' in capsys.readouterr().out


def test_web_progress_is_current_readable_and_does_not_modify_ordinary_state(driver, tmp_path, monkeypatch):
    import time
    from nsgablack.catalog.curation_progress import ENV, read_progress, status_message
    path, before = ordinary(driver, tmp_path)
    docker = FakeDocker(1)
    progress_path = tmp_path / "automation/progress/progress.json"
    monkeypatch.setenv(ENV, str(progress_path))
    entries = {item["key"]: item["digest"] for item in docker.probe["entries"]}
    def worker(image, **kw):
        value = json.loads(progress_path.read_text())
        assert value["status"] == "catching_up" and value["current"] == 0
        assert value["reserved_today"] == 658 and value["image_id"] == docker.image_id
        assert value["source_index_sha256"] == docker.probe["source_index_sha256"]
        assert value["prompt_version"] == docker.probe["prompt"]
        assert "正在补齐" in status_message(read_progress(entries, prompt_version=docker.probe["prompt"]))
        return success_worker(docker)(image, **kw)
    result = execute(driver, tmp_path, docker, worker, now=time.time())
    visible = read_progress(entries, prompt_version=docker.probe["prompt"])
    assert result["complete"] and visible["status"] == "complete" and visible["current"] == 1
    assert "已全部整理" in status_message(visible)
    assert path.read_bytes() == before
    public = json.loads(progress_path.read_text())
    assert not ({"job_id", "targets", "identity", "ordinary_at_start", "last_failure", "report_ref"} & public.keys())
    assert not read_progress({"another": "f" * 64}, prompt_version=docker.probe["prompt"])["available"]
    assert not read_progress(entries, prompt_version="wrong-prompt")["available"]


@pytest.mark.parametrize("error,expected", [("ai_http_403", "circuit_open"), ("ai_transport_failed", "backoff")])
def test_public_progress_explains_real_stops_instead_of_old_drain(driver, tmp_path, monkeypatch, error, expected):
    from nsgablack.catalog.curation_progress import ENV, read_progress
    docker = FakeDocker(1)
    path = tmp_path / "automation/progress/progress.json"
    monkeypatch.setenv(ENV, str(path))
    execute(driver, tmp_path, docker, lambda image, **kw: {"results": [
        {"entry_key": key, "error": error} for key in kw["keys"]]})
    public = json.loads(path.read_text())
    visible = read_progress({item["key"]: item["digest"] for item in docker.probe["entries"]},
                            prompt_version=docker.probe["prompt"])
    assert public["status"] == visible["status"] == expected
    assert public["current"] == 0 and public["remaining"] == 1
    assert "next_at" in visible and visible["available"]
    assert "error" not in public and "provider_diagnostics" not in public


def test_public_complete_waits_for_the_independent_exact_557_confirmation(driver, tmp_path):
    docker = FakeDocker(557)
    for item in docker.probe["entries"]:
        item["cached"] = True
    path = tmp_path / "automation/progress/progress.json"
    original = docker.run
    def probe(image, *, probe):
        if docker.probes == 1:
            assert not path.exists()  # First read alone cannot publish a complete message.
        return original(image, probe=probe)
    docker.run = probe
    result = execute(driver, tmp_path, docker, success_worker(docker))
    public = json.loads(path.read_text())
    assert result["complete"] and docker.probes == 2
    assert public["status"] == "complete" and public["current"] == public["total"] == 557


def test_failed_confirmation_cannot_publish_a_complete_web_message(driver, tmp_path):
    docker = FakeDocker(557)
    for item in docker.probe["entries"]:
        item["cached"] = True
    original = docker.run
    def probe(image, *, probe):
        if docker.probes == 1:
            docker.probe["entries"][0]["cached"] = False
        return original(image, probe=probe)
    docker.run = probe
    result = execute(driver, tmp_path, docker, success_worker(docker))
    public = json.loads((tmp_path / "automation/progress/progress.json").read_text())
    assert not result["complete"] and public["status"] == "partial"
    assert public["current"] == 556 and public["remaining"] == 1


def test_default_plan_does_not_probe_send_reserve_or_create_directories(driver, tmp_path, monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("A local plan cannot load Docker, a worker, or any credentials")
    monkeypatch.setattr(driver, "sibling", forbidden)
    result = driver.run_job(tmp_path, job_id="all557", docker=object(), worker=forbidden)
    assert result["status"] == "plan" and not result["complete"]
    assert result["execute_required"] and result["fresh_probe_required"]
    assert result["max_batches"] == 1 and result["reservation_upper_bound"] == 20
    assert not list(tmp_path.iterdir())


def test_existing_plan_is_read_only_and_never_claims_previous_complete_is_fresh(driver, tmp_path, monkeypatch):
    docker = FakeDocker(1)
    assert execute(driver, tmp_path, docker, success_worker(docker))["complete"]
    before = {path: path.read_bytes() for path in tmp_path.rglob("*.json")}
    def forbidden(*args, **kwargs):
        raise AssertionError("Planning must not probe even an existing job")
    monkeypatch.setattr(driver, "sibling", forbidden)
    result = driver.run_job(tmp_path, job_id="all557", expected_total=1, worker=forbidden)
    assert result["status"] == "plan" and not result["complete"]
    assert result["observed_status"]["complete"] and result["fresh_probe_required"]
    assert {path: path.read_bytes() for path in tmp_path.rglob("*.json")} == before


def test_explicit_execution_defaults_to_one_batch_and_resumes_same_ledger(driver, tmp_path):
    docker, calls = FakeDocker(23), []
    path, before = ordinary(driver, tmp_path)
    good = success_worker(docker)
    def worker(image, *, keys, feedback, report_dir, job_id, batch_id):
        calls.append(keys)
        return good(image, keys=keys, feedback=feedback, report_dir=report_dir, job_id=job_id, batch_id=batch_id)
    result = driver.run_job(tmp_path, job_id="all557", docker=docker, worker=worker,
                            execute=True, expected_total=23, now=100000)
    assert result["status"] == "batch_limit" and not result["complete"]
    assert result["current"] == 20 and result["reserved"] == 20 and result["batches_executed"] == 1
    assert len(calls) == 1 and path.read_bytes() == before
    result = driver.run_job(tmp_path, job_id="all557", docker=docker, worker=worker,
                            execute=True, expected_total=23, now=100001)
    assert result["complete"] and result["reserved"] == 23 and [len(keys) for keys in calls] == [20, 3]
    assert path.read_bytes() == before


def test_default_real_worker_gets_explicit_permission_without_changing_fake_contract(driver, tmp_path, monkeypatch):
    from types import SimpleNamespace
    docker, calls = FakeDocker(1), []
    original = driver.sibling
    def run(image, *, execute=False, **kwargs):
        assert execute is True
        calls.append(execute)
        return success_worker(docker)(image, **kwargs)
    monkeypatch.setattr(driver, "sibling", lambda name: SimpleNamespace(run=run) if name == "completion_worker" else original(name))
    result = driver.run_job(tmp_path, job_id="all557", docker=docker, execute=True, expected_total=1)
    assert result["complete"] and calls == [True]


def test_cli_without_execute_only_plans_and_does_not_need_root_or_lock(driver, tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(driver.os, "geteuid", lambda: 1234, raising=False)
    monkeypatch.setattr(driver, "run_job", lambda *a, **kw: pytest.fail("Planning CLI must not execute"))
    assert driver.main(["--root", str(tmp_path), "--job-id", "all557", "--wait-seconds", "86400"]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["status"] == "plan" and result["batches_executed"] == 0
    assert not list(tmp_path.iterdir())


def test_cli_wait_never_renews_its_explicit_batch_allowance(driver, tmp_path, monkeypatch, capsys):
    import sys
    from types import SimpleNamespace
    monkeypatch.setattr(driver.os, "geteuid", lambda: 0, raising=False)
    monkeypatch.setitem(sys.modules, "fcntl", SimpleNamespace(LOCK_EX=2, LOCK_NB=4, flock=lambda *a: None))
    monkeypatch.setattr(driver.signal, "signal", lambda *args: None)
    calls = []
    def run(*args, **kwargs):
        calls.append(kwargs)
        return {"complete": False, "status": "backoff", "batches_executed": 1, "next_eligible_at": 0}
    monkeypatch.setattr(driver, "run_job", run)
    monkeypatch.setattr(driver.time, "sleep", lambda _: None)
    assert driver.main(["--root", str(tmp_path), "--job-id", "all557", "--execute",
                        "--max-batches", "2", "--wait-seconds", "600"]) == 2
    assert [call["max_batches"] for call in calls] == [2, 1]
    assert all(call["execute"] is True for call in calls)
    capsys.readouterr()
