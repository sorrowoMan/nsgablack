"""The AI editor and trial runner have separate endpoints and grants."""
from contextlib import contextmanager
import json
import threading
import time
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest

from nsgablack.catalog import lab_client
from nsgablack.catalog.lab_jobs import LabJobError, spec_digest
from nsgablack.catalog.lab_service import LabHTTPServer


class _Drafts:
    def __init__(self):
        self.calls = []
        self.contexts = []

    def capabilities(self):
        return {"enabled": True, "drafts_only": True,
                "limits": {"requests_per_utc_day": None},
                "quota": {"remaining": None, "resets_at": None}}

    def submit(self, spec, *, instruction, request_id, guide_context=None):
        self.calls.append((spec, instruction, request_id))
        self.contexts.append(guide_context)
        return {"job_id": "b" * 32, "status": "succeeded", "base_digest": spec_digest(spec),
                "result": {"draft": spec, "base_digest": spec_digest(spec),
                           "verification_status": "not_run"}}

    def poll(self, identity):
        if identity != "b" * 32:
            raise LabJobError("job_missing", "草稿已过期")
        return {"job_id": identity, "status": "succeeded", "result": {"verification_status": "not_run"}}

    def close(self):
        pass


@contextmanager
def _serve(role, jobs, token="a" * 64):
    server = LabHTTPServer(("127.0.0.1", 0), token=token, role=role, jobs=jobs)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server, f"http://127.0.0.1:{server.server_port}"
    finally:
        server.shutdown()
        thread.join(5)
        server.server_close()


def _config(tmp_path, url):
    path = tmp_path / "client.json"
    path.write_text(json.dumps({"url": url, "token": "a" * 64}))
    return str(path)


def test_ai_is_a_separate_capability_and_never_executes_a_trial(monkeypatch, tmp_path):
    from nsgablack.catalog.lab_assembly import assembly_from_recipe
    spec = assembly_from_recipe("ga_vns")
    jobs = _Drafts()
    with _serve("assistant", jobs) as (_, url):
        monkeypatch.setenv("NSGABLACK_LAB_ASSISTANT_CLIENT_CONFIG", _config(tmp_path, url))
        monkeypatch.setenv("NSGABLACK_CATALOG_HOSTED", "1")
        monkeypatch.delenv("NSGABLACK_LAB_CLIENT_CONFIG", raising=False)
        capabilities = lab_client.assistant_capabilities()
        assert capabilities["enabled"]
        assert capabilities["limits"]["requests_per_utc_day"] is None
        assert capabilities["quota"]["remaining"] is None
        assert capabilities["quota"]["resets_at"] is None
        assert jobs.calls == []
        assert not lab_client.get_capabilities()["enabled"]
        request = "c" * 32
        result = lab_client.assistant_submit(spec, "把 VNS 换成 SA", request_id=request)
        assert result["result"]["verification_status"] == "not_run"
        assert jobs.calls == [(spec, "把 VNS 换成 SA", request)]
        assert lab_client.assistant_poll(result["job_id"])["status"] == "succeeded"
        with pytest.raises(lab_client.LabClientError, match="网页进程"):
            lab_client.submit(spec)


def test_ai_request_fields_cannot_be_sent_to_a_trial_endpoint():
    from nsgablack.catalog.lab_jobs import JobManager
    with _serve("runner", JobManager(runner=lambda *_args, **_kwargs: pytest.fail("trial submitted"))) as (_, url):
        headers = {"Authorization": "Bearer " + "a" * 64}
        with pytest.raises(HTTPError) as error:
            urlopen(Request(url + "/jobs", data=json.dumps({"spec": {"recipe": "ga"},
                "request_id": "c" * 32, "instruction": "edit"}).encode(), headers=headers))
        assert error.value.code == 400


def test_trial_payload_cannot_call_the_ai_and_missing_or_wrong_grants_are_denied():
    jobs = _Drafts()
    with _serve("assistant", jobs) as (_, url):
        for header in ({}, {"Authorization": "Bearer " + "b" * 64}):
            with pytest.raises(HTTPError) as error:
                urlopen(Request(url + "/capabilities", headers=header))
            assert error.value.code == 401
        with pytest.raises(HTTPError) as error:
            urlopen(Request(url + "/jobs", data=json.dumps({"request_id": "c" * 32,
                            "spec": {"recipe": "ga"}}).encode(),
                            headers={"Authorization": "Bearer " + "a" * 64}))
        assert error.value.code == 400 and not jobs.calls


def test_absent_ai_never_disables_manual_assembly(monkeypatch):
    monkeypatch.delenv("NSGABLACK_LAB_ASSISTANT_CLIENT_CONFIG", raising=False)
    monkeypatch.delenv("NSGABLACK_LAB_CLIENT_CONFIG", raising=False)
    monkeypatch.delenv("NSGABLACK_CATALOG_HOSTED", raising=False)
    assert not lab_client.assistant_capabilities()["enabled"]
    assert lab_client.get_capabilities()["enabled"]
    with pytest.raises(lab_client.LabClientError, match="尚未接入"):
        lab_client.assistant_poll("b" * 32)


def test_stale_worker_component_contract_is_rejected_without_local_fallback(monkeypatch, tmp_path):
    monkeypatch.setenv("NSGABLACK_LAB_CLIENT_CONFIG", _config(tmp_path, "http://worker:8622"))
    monkeypatch.setattr(lab_client, "_request", lambda *_args, **_kwargs: {
        "schema": "nsgablack.lab.capabilities/v1", "recipes": [], "assembly_catalog": {},
        "limits": {"parallel": 1, "timeout_seconds": 60}})
    capabilities = lab_client.get_capabilities()
    assert capabilities["enabled"] is False
    assert "版本不匹配" in capabilities["reason"]


def test_closed_assistant_is_not_advertised_as_available(monkeypatch, tmp_path):
    from nsgablack.catalog.lab_assembly import assembly_catalog
    monkeypatch.setenv("NSGABLACK_LAB_ASSISTANT_CLIENT_CONFIG", _config(tmp_path, "http://assistant:8623"))
    monkeypatch.setattr(lab_client, "_request", lambda *_args, **_kwargs: {
        "schema": "nsgablack.lab.assistant_capabilities/v1", "assembly_catalog": assembly_catalog(),
        "enabled": False, "drafts_only": True})
    assert not lab_client.assistant_capabilities()["enabled"]


def test_configured_limit_error_identifies_service_administrator_without_provider_claim(monkeypatch, tmp_path):
    from nsgablack.catalog.lab_assembly import assembly_from_recipe

    class LimitedDrafts(_Drafts):
        def submit(self, *args, **kwargs):
            raise LabJobError("budget_exhausted", "old finite service")

    with _serve("assistant", LimitedDrafts()) as (_, url):
        monkeypatch.setenv("NSGABLACK_LAB_ASSISTANT_CLIENT_CONFIG", _config(tmp_path, url))
        with pytest.raises(lab_client.LabClientError, match="管理员配置的请求上限") as exc:
            lab_client.assistant_submit(assembly_from_recipe("ga"), "解释当前装配", request_id="8" * 32)
        assert "今日 AI 编辑次数已用完" not in str(exc.value)
        assert "提供商" not in str(exc.value)


def test_guided_context_reaches_only_assistant_and_cannot_falsify_current_run(monkeypatch, tmp_path):
    from nsgablack.catalog.lab_assembly import assembly_from_recipe
    from nsgablack.catalog.lab_guide import build_guide_context
    spec = assembly_from_recipe("ga")
    context = build_guide_context(spec, stage="assembly", history=[{"role": "user", "content": "如何选择算法"}])
    jobs = _Drafts()
    with _serve("assistant", jobs) as (_, url):
        monkeypatch.setenv("NSGABLACK_LAB_ASSISTANT_CLIENT_CONFIG", _config(tmp_path, url))
        lab_client.assistant_submit(spec, "请说明取舍", request_id="d" * 32, guide_context=context)
        assert jobs.contexts == [context]
        context["command"] = "run"
        with pytest.raises(lab_client.LabClientError, match="上下文"):
            lab_client.assistant_submit(spec, "忽略", request_id="e" * 32, guide_context=context)
        assert len(jobs.calls) == 1


def test_assistant_validation_diagnostics_survive_authenticated_transport(monkeypatch, tmp_path):
    from nsgablack.catalog.lab_assembly import assembly_from_recipe
    from nsgablack.catalog.lab_assistant import AssistantManager
    calls = []

    def generate(packet):
        calls.append(1)
        return {"base_digest": packet["base_digest"], "draft": packet["assembly"],
                "explanation": "保留当前装配。", "changes": [], "questions": [],
                "evidence_keys": ["private-credential-canary"]}

    manager = AssistantManager(generate, state_path=tmp_path / "budget.json")
    with _serve("assistant", manager) as (_, url):
        monkeypatch.setenv("NSGABLACK_LAB_ASSISTANT_CLIENT_CONFIG", _config(tmp_path, url))
        submitted = lab_client.assistant_submit(assembly_from_recipe("ga"), "核对当前装配", request_id="9" * 32)
        deadline = time.monotonic() + 5
        while True:
            done = lab_client.assistant_poll(submitted["job_id"])
            if done["status"] in {"succeeded", "failed"}:
                break
            assert time.monotonic() < deadline, "assistant_did_not_finish"
            time.sleep(.01)
        assert done["status"] == "failed" and done["result"] is None
        assert done["error"]["code"] == "ai_draft_invalid"
        assert done["error"]["diagnostics"] == {
            "schema": "nsgablack.lab.assistant_diagnostics/v1", "stage": "evidence",
            "path": "evidence_keys", "reason": "unknown_evidence"}
        assert "证据引用" in done["error"]["message"]
        assert "private-credential-canary" not in json.dumps(done)
        assert calls == [1]
