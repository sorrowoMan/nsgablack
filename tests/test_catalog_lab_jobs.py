import json
import threading
import time
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest

from nsgablack.catalog import lab_client
from nsgablack.catalog.lab_jobs import JobManager, LabJobError
from nsgablack.catalog.lab_service import LabHTTPServer


def _done(jobs, job_id):
    limit = time.monotonic() + 5
    while time.monotonic() < limit:
        value = jobs.poll(job_id)
        if value["status"] in {"succeeded", "failed"}:
            return value
        time.sleep(.01)
    raise AssertionError("job_did_not_finish")


def test_same_request_executes_once_and_cannot_change_spec():
    calls = []
    def runner(spec, **kwargs):
        calls.append(spec)
        return {"status": "succeeded", "steps": 2}
    manager = JobManager(runner=runner)
    try:
        first = manager.submit({"recipe": "ga"}, request_id="a" * 32)
        again = manager.submit({"recipe": "ga"}, request_id="a" * 32)
        assert first["job_id"] == again["job_id"]
        final = _done(manager, first["job_id"])
        final["spec"]["seed"] = -1
        assert manager.poll(first["job_id"])["spec"]["seed"] >= 0
        assert len(calls) == 1
        with pytest.raises(LabJobError, match="不能更换"):
            manager.submit({"recipe": "vns"}, request_id="a" * 32)
    finally:
        manager.close()


def test_queue_has_one_active_worker_and_a_finite_pending_limit():
    release, entered = threading.Event(), threading.Event()
    active = []
    def runner(spec, **kwargs):
        active.append(spec)
        entered.set()
        release.wait(5)
        return {"status": "succeeded"}
    manager = JobManager(runner=runner, max_pending=2)
    try:
        first = manager.submit({"recipe": "ga"}, request_id="a" * 32)
        assert entered.wait(2)
        second = manager.submit({"recipe": "vns"}, request_id="b" * 32)
        assert manager.poll(second["job_id"])["status"] == "queued"
        with pytest.raises(LabJobError) as error:
            manager.submit({"recipe": "moead"}, request_id="c" * 32)
        assert error.value.code == "queue_full"
        assert len(active) == 1
        release.set()
        assert _done(manager, first["job_id"])["status"] == "succeeded"
        assert _done(manager, second["job_id"])["status"] == "succeeded"
    finally:
        release.set()
        manager.close()


def test_worker_failure_does_not_expose_exception_or_block_next_trial():
    def runner(spec, **kwargs):
        if spec["recipe"] == "ga":
            raise RuntimeError("private://secret")
        return {"status": "succeeded"}
    manager = JobManager(runner=runner)
    try:
        job = manager.submit({"recipe": "ga"}, request_id="a" * 32)
        result = _done(manager, job["job_id"])
        assert result["status"] == "failed"
        assert "private" not in json.dumps(result)
        assert _done(manager, manager.submit({"recipe": "vns"}, request_id="b" * 32)["job_id"])["status"] == "succeeded"
        with pytest.raises(LabJobError):
            manager.poll("../not-a-job")
        with pytest.raises(LabJobError, match="过期"):
            manager.poll("0" * 32)
    finally:
        manager.close()


@pytest.fixture
def service():
    calls = []
    def runner(spec, **kwargs):
        calls.append(spec)
        return {"status": "succeeded", "steps": 2}
    server = LabHTTPServer(("127.0.0.1", 0), token="a" * 64, jobs=JobManager(runner=runner))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server, f"http://127.0.0.1:{server.server_port}", calls
    finally:
        server.shutdown()
        thread.join(5)
        server.server_close()


def test_private_worker_auth_and_command_boundary(service):
    server, url, calls = service
    with pytest.raises(HTTPError) as error:
        urlopen(url + "/capabilities")
    assert error.value.code == 401
    token = {"Authorization": "Bearer " + "a" * 64, "Content-Type": "application/json"}
    malicious = {"request_id": "a" * 32, "spec": {"recipe": "ga", "command": "anything"}}
    with pytest.raises(HTTPError) as error:
        urlopen(Request(url + "/jobs", data=json.dumps(malicious).encode(), headers=token))
    assert error.value.code == 400 and calls == []
    with pytest.raises(HTTPError) as error:
        urlopen(Request(url + "/jobs", data=b"x" * 16385, headers=token))
    assert error.value.code == 400
    capabilities = json.load(urlopen(Request(url + "/capabilities", headers=token)))
    assert capabilities["limits"]["parallel"] == 1
    assert len(capabilities["recipes"]) >= 3
    assert "a" * 64 not in json.dumps(capabilities)


def test_hosted_without_worker_cannot_fall_back_to_local(monkeypatch):
    monkeypatch.setenv("NSGABLACK_CATALOG_HOSTED", "1")
    monkeypatch.delenv("NSGABLACK_LAB_CLIENT_CONFIG", raising=False)
    assert lab_client.get_capabilities()["enabled"] is False
    with pytest.raises(lab_client.LabClientError, match="网页进程"):
        lab_client.submit({"recipe": "ga"})


def test_remote_client_submits_only_structured_spec_and_reads_real_job(service, monkeypatch, tmp_path):
    server, url, calls = service
    path = tmp_path / "worker.json"
    path.write_text(json.dumps({"url": url, "token": "a" * 64}))
    monkeypatch.setenv("NSGABLACK_LAB_CLIENT_CONFIG", str(path))
    monkeypatch.setenv("NSGABLACK_CATALOG_HOSTED", "1")
    assert lab_client.get_capabilities()["mode"] == "remote"
    submitted = lab_client.submit({"recipe": "ga"})
    result = _done(server.jobs, submitted["job_id"])
    assert lab_client.poll(submitted["job_id"])["status"] == result["status"] == "succeeded"
    assert calls[0]["recipe"] == "ga"
    with pytest.raises(lab_client.LabClientError):
        lab_client.poll("../../secret")


def test_lost_submit_response_can_be_retried_without_repeating_the_project(service, monkeypatch, tmp_path):
    server, url, calls = service
    config = tmp_path / "worker.json"
    config.write_text(json.dumps({"url": url, "token": "a" * 64}))
    monkeypatch.setenv("NSGABLACK_LAB_CLIENT_CONFIG", str(config))
    original = lab_client._request
    attempts = []
    def response_lost_once(*args, **kwargs):
        result = original(*args, **kwargs)
        attempts.append(result)
        if len(attempts) == 1:
            raise lab_client.LabClientError("connection lost after server acceptance")
        return result
    monkeypatch.setattr(lab_client, "_request", response_lost_once)
    with pytest.raises(lab_client.LabClientError):
        lab_client.submit({"recipe": "ga"}, request_id="c" * 32)
    recovered = lab_client.submit({"recipe": "ga"}, request_id="c" * 32)
    assert recovered["job_id"] == attempts[0]["job_id"]
    assert _done(server.jobs, recovered["job_id"])["status"] == "succeeded"
    assert len(calls) == 1


@pytest.mark.parametrize("url", ["https://worker:8080", "http://user:pass@worker:8080", "http://worker:8080/path", "file:///tmp/secret"])
def test_worker_destination_is_only_fixed_deployment_endpoint(monkeypatch, tmp_path, url):
    config = tmp_path / "worker.json"
    config.write_text(json.dumps({"url": url, "token": "a" * 64}))
    monkeypatch.setenv("NSGABLACK_LAB_CLIENT_CONFIG", str(config))
    assert lab_client.get_capabilities()["enabled"] is False
