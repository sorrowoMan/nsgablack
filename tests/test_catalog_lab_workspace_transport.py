"""Loopback transport keeps code execution on the authenticated local agent."""
from contextlib import contextmanager
from copy import deepcopy
import http.client
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
import socket
from pathlib import Path
import subprocess
import sys
import threading
from types import SimpleNamespace
from urllib.error import URLError

import pytest

from nsgablack.catalog import lab_workspace_transport as transport


TOKEN = "a" * 64
WID, RID, JOB, REQUEST = "1" * 32, "2" * 32, "3" * 32, "4" * 32


class Recorder:
    def __init__(self):
        self.calls = []
        self.responses = {}
        self.failures = {}

    def __getattr__(self, name):
        def call(**arguments):
            self.calls.append((name, deepcopy(arguments)))
            if name in self.failures:
                raise self.failures[name]
            return deepcopy(self.responses.get(name, {"operation": name, "arguments": arguments}))
        return call


@contextmanager
def running(store=None, runner=None):
    store = store if store is not None else Recorder()
    runner = runner if runner is not None else Recorder()
    server = transport.WorkspaceAgentServer(("127.0.0.1", 0), token=TOKEN, store=store, runner=runner)
    worker = threading.Thread(target=lambda: server.serve_forever(poll_interval=.01), daemon=True)
    worker.start()
    endpoint = "http://127.0.0.1:" + str(server.server_port)
    try:
        yield SimpleNamespace(server=server, store=store, runner=runner, endpoint=endpoint,
                              client=transport.WorkspaceRPCClient(endpoint, TOKEN, timeout_seconds=3))
    finally:
        server.shutdown()
        server.server_close()
        worker.join(timeout=3)


def raw(agent, body, *, token=TOKEN, headers=None):
    selected = {"Content-Type": "application/json", **(headers or {})}
    if token is not None:
        selected["Authorization"] = "Bearer " + token
    if "Content-Length" not in selected and "Transfer-Encoding" not in selected:
        selected["Content-Length"] = str(len(body))
    # Header-only refusals must race neither a second client write nor Windows'
    # reset of a half-sent request. Send this deliberately malformed fixture in
    # one packet; production RPC validation and refusal assertions stay intact.
    lines = ["POST /rpc HTTP/1.1", f"Host: 127.0.0.1:{agent.server.server_port}",
             *(f"{name}: {value}" for name, value in selected.items()), "", ""]
    with socket.create_connection(("127.0.0.1", agent.server.server_port), timeout=3) as connection:
        connection.sendall("\r\n".join(lines).encode("latin-1") + body)
        response = http.client.HTTPResponse(connection)
        response.begin()
        value = json.loads(response.read())
        return response.status, value


def packet(operation, arguments):
    return json.dumps({"operation": operation, "arguments": arguments}, ensure_ascii=False).encode("utf-8")


@pytest.mark.parametrize("operation,arguments,role", [
    ("list_sources", {}, "store"),
    ("create_workspace", {"project_id": "examples:demo", "title": "中文工程"}, "store"),
    ("list_workspaces", {}, "store"),
    ("get_workspace", {"workspace_id": WID}, "store"),
    ("get_revision", {"workspace_id": WID, "revision_id": None}, "store"),
    ("list_revisions", {"workspace_id": WID}, "store"),
    ("read_file", {"workspace_id": WID, "revision_id": RID, "path": "cases/search/problem.py"}, "store"),
    ("save_files", {"workspace_id": WID, "changes": {"cases/search/problem.py": "# 中文\nx = 1\n"},
                    "expected_revision": RID, "message": "保存"}, "store"),
    ("parameter_schema", {"workspace_id": WID, "revision_id": RID, "case_name": "search"}, "runner"),
    ("check", {"workspace_id": WID, "revision_id": RID, "case_name": "search", "parameters": {},
               "max_steps": 2, "seed": 42, "timeout_seconds": 60}, "runner"),
    ("submit", {"workspace_id": WID, "revision_id": RID, "case_name": "search", "request_id": REQUEST}, "runner"),
    ("get_job", {"workspace_id": WID, "job_id": JOB}, "runner"),
])
def test_authenticated_operations_preserve_their_exact_arguments(operation, arguments, role):
    with running() as agent:
        result = agent.client.call(operation, arguments)
        assert result == {"operation": operation, "arguments": arguments}
        assert getattr(agent, role).calls == [(operation, arguments)]
        assert getattr(agent, "runner" if role == "store" else "store").calls == []


def test_job_list_is_a_thin_history_projection_and_full_get_is_unchanged():
    runner = Recorder()
    complete = {"job_id": JOB, "workspace_id": WID, "revision_id": RID, "status": "succeeded",
                "result": {"steps": 2, "evaluations": 7, "elapsed_seconds": 1.2,
                           "raw_results": {"raw_objectives": [[2.625]]},
                           "artifact_archive": {"base64": "large-example-payload"}}}
    runner.responses = {"list_jobs": [complete], "get_job": complete}
    with running(runner=runner) as agent:
        remote = transport.RemoteWorkspaceRunner(agent.client)
        summaries = remote.list_jobs(WID)
        assert summaries[0]["result_is_summary"]
        assert summaries[0]["result"] == {"steps": 2, "evaluations": 7, "elapsed_seconds": 1.2}
        assert remote.get_job(WID, JOB) == complete
        assert "artifact_archive" in complete["result"], "Projection must not mutate the stored result"


def test_remote_facades_match_the_existing_ui_call_signatures():
    client = SimpleNamespace(endpoint="http://127.0.0.1:18640", calls=[])
    def call(operation, arguments):
        client.calls.append((operation, arguments))
        return operation
    client.call = call
    store, runner = transport.RemoteWorkspaceStore(client), transport.RemoteWorkspaceRunner(client)
    assert store.list_sources() == "list_sources"
    assert store.create_workspace("examples:demo") == "create_workspace"
    assert store.list_workspaces() == "list_workspaces"
    assert store.get_workspace(WID) == "get_workspace"
    assert store.get_revision(WID) == "get_revision"
    assert store.list_revisions(WID) == "list_revisions"
    assert store.read_file(WID, RID, "problem.py") == "read_file"
    assert store.save_files(WID, {"problem.py": "pass\n"}, expected_revision=RID) == "save_files"
    assert runner.parameter_schema(WID, RID, "search") == "parameter_schema"
    assert runner.check(WID, RID, "search") == "check"
    assert runner.submit(WID, RID, "search", request_id=REQUEST) == "submit"
    assert runner.get_job(WID, JOB) == "get_job"
    assert runner.list_jobs(WID) == "list_jobs"
    assert len(client.calls) == 13
    assert client.calls[9][1]["timeout_seconds"] == 60
    assert client.calls[10][1]["request_id"] == REQUEST
    assert str(store.root).endswith(hashlib_id(client.endpoint))
    assert not store.root.exists()


def hashlib_id(endpoint):
    import hashlib
    return hashlib.sha256(endpoint.encode()).hexdigest()[:16]


@pytest.mark.parametrize("token", [None, "b" * 64, "", "not-an-agent-key"])
def test_unauthorized_requests_cannot_observe_or_mutate_the_workspace(token):
    with running() as agent:
        status, value = raw(agent, packet("list_workspaces", {}), token=token)
        assert status == 401 and value["error"]["code"] == "workspace_unauthorized"
        assert agent.store.calls == agent.runner.calls == []


def test_health_discloses_no_project_roots_and_browser_rpc_is_refused():
    with running() as agent:
        connection = http.client.HTTPConnection("127.0.0.1", agent.server.server_port, timeout=3)
        connection.request("GET", "/health")
        response = connection.getresponse()
        assert response.status == 200 and json.loads(response.read()) == {"ok": True}
        connection.close()
        status, value = raw(agent, packet("list_sources", {}), headers={"Origin": "https://example.test"})
        assert status == 403 and value["error"]["code"] == "workspace_browser_rpc_refused"
        assert not agent.store.calls


@pytest.mark.parametrize("operation,arguments", [
    ("shutdown", {}), ("materialize", {"target": "C:/outside"}), ("__dict__", {}),
    ("get_workspace", {"workspace_id": WID, "root": "C:/outside"}),
    ("list_sources", {"endpoint": "http://example.test"}),
    ("read_file", {"workspace_id": WID, "revision_id": RID, "path": "../secret.py"}),
    ("read_file", {"workspace_id": WID, "revision_id": RID, "path": "C:/secret.py"}),
    ("read_file", {"workspace_id": WID, "revision_id": RID, "path": "cases\\search.py"}),
    ("get_job", {"workspace_id": WID, "job_id": "../job"}),
    ("check", {"workspace_id": WID, "revision_id": RID, "case_name": "search", "max_steps": True}),
    ("submit", {"workspace_id": WID, "revision_id": RID, "case_name": "search", "request_id": REQUEST, "command": "do anything"}),
])
def test_closed_operation_and_field_contract_rejects_before_backend_dispatch(operation, arguments):
    with running() as agent:
        status, value = raw(agent, packet(operation, arguments))
        assert status == 400 and not value["ok"]
        assert agent.store.calls == agent.runner.calls == []


@pytest.mark.parametrize("body", [
    b'{"operation":"list_sources","operation":"list_workspaces","arguments":{}}',
    b'{"operation":"list_sources","arguments":{},"path":"C:/private"}',
    b'{"operation":"check","arguments":{"workspace_id":"' + WID.encode() + b'","revision_id":"' + RID.encode()
        + b'","case_name":"search","parameters":{"a":1,"a":2}}}',
    b'{"operation":"check","arguments":{"workspace_id":"' + WID.encode() + b'","revision_id":"' + RID.encode()
        + b'","case_name":"search","parameters":{"a":NaN}}}',
    b'{"operation":"check","arguments":{"workspace_id":"' + WID.encode() + b'","revision_id":"' + RID.encode()
        + b'","case_name":"search","parameters":{"a":1e999}}}',
    b'[]', b'\xff',
])
def test_strict_json_rejects_nonfinite_duplicate_or_invalid_payloads(body):
    with running() as agent:
        status, value = raw(agent, body)
        assert status == 400 and not value["ok"]
        assert not agent.store.calls and not agent.runner.calls


@pytest.mark.parametrize("headers", [
    {"Content-Length": str(transport.MAX_REQUEST_BYTES + 1)},
    {"Content-Length": "0"}, {"Transfer-Encoding": "chunked"}, {"Content-Type": "text/plain"},
])
def test_request_body_limits_are_checked_before_dispatch(headers):
    with running() as agent:
        status, value = raw(agent, b"null", headers=headers)
        assert status == 400 and not value["ok"]
        assert not agent.store.calls


@pytest.mark.parametrize("address", [("0.0.0.0", 0), ("192.168.1.1", 8000), ("example.test", 8000)])
def test_agent_cannot_bind_public_interfaces(address):
    with pytest.raises(transport.WorkspaceConnectionError, match="回环"):
        transport.WorkspaceAgentServer(address, token=TOKEN, store=Recorder(), runner=Recorder())


@pytest.mark.parametrize("endpoint", [
    "https://127.0.0.1:8640", "http://8.217.114.28:8640", "http://0.0.0.0:8640",
    "http://user:pass@127.0.0.1:8640", "http://127.0.0.1:8640/custom",
    "http://127.0.0.1:8640?token=anything", "http://127.0.0.1:8640/#fragment", "http://localhost",
])
def test_client_endpoint_is_fixed_loopback_configuration(endpoint):
    with pytest.raises(transport.WorkspaceConnectionError):
        transport.WorkspaceRPCClient(endpoint, TOKEN)


def test_offline_client_never_retries_or_falls_back_to_local_execution():
    client = transport.WorkspaceRPCClient("http://127.0.0.1:18640", TOKEN)
    calls = []
    def unavailable(*args, **kwargs):
        calls.append(args)
        raise URLError("private network diagnostics must not escape")
    client._opener = SimpleNamespace(open=unavailable)
    with pytest.raises(transport.WorkspaceConnectionError) as error:
        transport.RemoteWorkspaceRunner(client).submit(WID, RID, "search", request_id=REQUEST)
    assert error.value.code == "workspace_agent_offline"
    assert "private network" not in str(error.value) and len(calls) == 1


@pytest.mark.parametrize("failure,code", [
    (OSError("C:/private/path/password.txt"), "workspace_agent_storage_unavailable"),
    (RuntimeError("private-model-key-and-path"), "workspace_agent_error"),
])
def test_unexpected_backend_failures_do_not_disclose_paths_or_secret_text(failure, code):
    with running() as agent:
        agent.store.failures["list_sources"] = failure
        with pytest.raises(transport.WorkspaceConnectionError) as error:
            agent.client.call("list_sources", {})
        assert error.value.code == code
        assert "private" not in str(error.value) and "password" not in str(error.value)


def test_domain_conflict_is_preserved_for_the_editor():
    from nsgablack.catalog.lab_workspace_store import WorkspaceError
    with running() as agent:
        agent.store.failures["save_files"] = WorkspaceError("workspace_revision_conflict", "Reload the current revision.")
        with pytest.raises(transport.WorkspaceConnectionError) as error:
            transport.RemoteWorkspaceStore(agent.client).save_files(WID, {"problem.py": "pass\n"}, expected_revision=RID)
        assert error.value.code == "workspace_revision_conflict"


def test_client_loader_imports_no_backend_or_project_modules(tmp_path):
    path = tmp_path / "client.json"
    path.write_text(json.dumps({"endpoint": "http://127.0.0.1:18640", "token": TOKEN}), encoding="utf-8")
    code = '''import importlib.abc,sys
class RefuseBackend(importlib.abc.MetaPathFinder):
 def find_spec(self,fullname,path=None,target=None):
  if fullname.endswith(("lab_workspace_store","lab_workspace_runner","lab_project_sources","lab_project_trial")):
   raise AssertionError("frontend tried to load backend")
sys.meta_path.insert(0,RefuseBackend())
from nsgablack.catalog.lab_workspace_transport import load_remote_runtime
runtime=load_remote_runtime(sys.argv[1])
assert runtime.mode=="remote"
assert not runtime.store.root.exists()
'''
    done = subprocess.run([sys.executable, "-c", code, str(path)], capture_output=True, timeout=20)
    assert done.returncode == 0, done.stderr.decode(errors="replace")


def test_loader_rejects_duplicate_or_unknown_config_fields(tmp_path):
    path = tmp_path / "client.json"
    path.write_text('{"endpoint":"http://127.0.0.1:18640","token":"' + TOKEN
                    + '","root":"C:/outside"}', encoding="utf-8")
    with pytest.raises(transport.WorkspaceConnectionError):
        transport.load_remote_runtime(path)
    path.write_text('{"token":"' + TOKEN + '","token":"' + TOKEN + '"}', encoding="utf-8")
    with pytest.raises(transport.WorkspaceConnectionError):
        transport.load_remote_runtime(path)


def test_real_store_roundtrip_never_imports_or_changes_the_source_project(tmp_path):
    from nsgablack.catalog.lab_project_sources import ProjectSourceRegistry
    from nsgablack.catalog.lab_workspace_store import WorkspaceStore
    source = tmp_path / "source"
    case = source / "cases" / "search"
    case.mkdir(parents=True)
    files = {"project_config.py": "PROJECT_NAME = 'sample'\n", "run_project.py": "raise RuntimeError('never run on read')\n",
             "cases/__init__.py": "", "cases/search/__init__.py": "",
             "cases/search/build_solver.py": "raise RuntimeError('never import on read')\n",
             "cases/search/run_solver.py": "raise RuntimeError('never import on read')\n",
             "cases/search/problem.py": "value = 1\n"}
    for relative, text in files.items():
        (source / relative).write_text(text, encoding="utf-8", newline="")
    store = WorkspaceStore(tmp_path / "data", ProjectSourceRegistry({"source": source}))
    with running(store=store) as agent:
        remote = transport.RemoteWorkspaceStore(agent.client)
        workspace = remote.create_workspace("source:.", title="真实只读来源")
        wid, rid = workspace["workspace_id"], workspace["head_revision"]
        assert remote.read_file(wid, rid, "cases/search/problem.py")["content"] == "value = 1\n"
        revision = remote.save_files(wid, {"cases/search/problem.py": "value = 2\n"}, expected_revision=rid)
        assert remote.get_workspace(wid)["head_revision"] == revision["revision_id"]
        assert remote.read_file(wid, revision["revision_id"], "cases/search/problem.py")["content"] == "value = 2\n"
        assert remote.read_file(wid, rid, "cases/search/problem.py")["content"] == "value = 1\n"
        assert (source / "cases/search/problem.py").read_text() == "value = 1\n"
        assert not agent.runner.calls


def test_redirect_responses_are_not_followed_with_the_agent_credential():
    calls = []
    class Redirect(BaseHTTPRequestHandler):
        def log_message(self, *_args):
            pass
        def do_POST(self):
            calls.append(self.path)
            self.send_response(302)
            self.send_header("Location", "/credential-target")
            self.send_header("Content-Length", "0")
            self.end_headers()
    server = ThreadingHTTPServer(("127.0.0.1", 0), Redirect)
    thread = threading.Thread(target=lambda: server.serve_forever(poll_interval=.01), daemon=True)
    thread.start()
    try:
        client = transport.WorkspaceRPCClient(f"http://127.0.0.1:{server.server_port}", TOKEN)
        with pytest.raises(transport.WorkspaceConnectionError):
            client.call("list_sources", {})
        assert calls == ["/rpc"]
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)
