from __future__ import annotations

import json
import threading
from urllib.error import HTTPError
from urllib.request import Request, build_opener, ProxyHandler

import pytest

from nsgablack.catalog.lab_service import LabHTTPServer
from nsgablack.catalog.lab_model_provider import complete_project_turn
from nsgablack.catalog.lab_assistant import AssistantProviderError, DeepSeekAssemblyGenerator
from nsgablack.catalog.curation_provider import DeepSeekConfig


class Jobs:
    def __init__(self):
        self.submissions = []

    def project_capabilities(self):
        return {"enabled": True, "projects": []}

    def poll(self, identity):
        return {"job_id": identity, "kind": "project", "status": "succeeded",
                "result": {"project_id": "examples:sample", "proposal_digest": "a" * 64}}

    def submit_project(self, spec, **kwargs):
        self.submissions.append((spec, kwargs))
        return {"job_id": "1" * 32, "status": "queued"}

    def close(self):
        pass


def request(server, path, token, body=None):
    data = None if body is None else json.dumps(body).encode()
    req = Request(f"http://127.0.0.1:{server.server_port}" + path, data=data,
                  headers={"Authorization": "Bearer " + token, "Content-Type": "application/json"})
    return build_opener(ProxyHandler({})).open(req, timeout=3)


def test_result_read_grant_cannot_submit_or_read_other_worker_surfaces():
    jobs = Jobs()
    server = LabHTTPServer(("127.0.0.1", 0), token="a" * 64,
                           result_token="b" * 64, jobs=jobs)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        with request(server, "/project/jobs/" + "1" * 32, "b" * 64) as response:
            assert json.load(response)["status"] == "succeeded"
        for path, body in (("/capabilities", None), ("/jobs/" + "1" * 32, None),
                           ("/project/jobs", {"request_id": "2" * 32, "spec": {}, "confirmed_digest": "c" * 64})):
            with pytest.raises(HTTPError) as exc:
                request(server, path, "b" * 64, body)
            assert exc.value.code == 401
        assert jobs.submissions == []
    finally:
        server.shutdown()
        server.server_close()
        thread.join(3)


def test_project_assistant_endpoint_does_not_accept_browser_fabricated_trial_metrics():
    jobs = Jobs()
    server = LabHTTPServer(("127.0.0.1", 0), token="a" * 64, jobs=jobs, role="assistant")
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        with request(server, "/project/jobs", "a" * 64, {
                "request_id": "1" * 32, "project_id": "examples:sample", "instruction": "读项目"}) as response:
            assert response.status == 202
        with pytest.raises(HTTPError) as exc:
            request(server, "/project/jobs", "a" * 64, {"request_id": "2" * 32,
                "project_id": "examples:sample", "instruction": "读结果", "metrics": {"total": 99999}})
        assert exc.value.code == 400
        assert len(jobs.submissions) == 1
    finally:
        server.shutdown()
        server.server_close()
        thread.join(3)


class Response:
    def __init__(self, value):
        self.data = json.dumps(value).encode()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def geturl(self):
        return "https://api.deepseek.com/chat/completions"

    def read(self, size):
        return self.data[:size]


class Opener:
    def __init__(self, value):
        self.value = value
        self.requests = []

    def open(self, request, timeout):
        self.requests.append(request)
        return Response(self.value)


def test_deepseek_tools_transport_sends_definitions_and_preserves_native_calls():
    opener = Opener({"model": "deepseek-flash", "choices": [{"finish_reason": "tool_calls",
        "message": {"role": "assistant", "content": None, "tool_calls": [{"id": "r1",
            "type": "function", "function": {"name": "project_files", "arguments": "{}"}}]}}]})
    generator = DeepSeekAssemblyGenerator(DeepSeekConfig(api_key="test-credential", model="deepseek-flash"), opener=opener)
    value = complete_project_turn(generator, [{"role": "user", "content": "JSON"}],
                                  [{"type": "function", "function": {"name": "project_files"}}])
    body = json.loads(opener.requests[0].data)
    assert body["tools"][0]["function"]["name"] == "project_files"
    assert body["thinking"] == {"type": "disabled"}
    assert value["message"]["tool_calls"][0]["id"] == "r1"
    assert len(opener.requests) == 1


def test_incomplete_tool_response_is_not_retried_or_used():
    opener = Opener({"choices": [{"finish_reason": "length", "message": {"content": "{}"}}]})
    generator = DeepSeekAssemblyGenerator(DeepSeekConfig(api_key="test-credential", model="deepseek-flash"), opener=opener)
    with pytest.raises(AssistantProviderError, match="ai_response_incomplete"):
        complete_project_turn(generator, [{"role": "user", "content": "JSON"}], [])
    assert len(opener.requests) == 1
