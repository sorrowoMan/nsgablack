"""Authenticated loopback transport for a frontend with a local Project agent.

Importing the client needs only the standard library. Project sources, writable
storage, and algorithm execution exist only inside the explicitly started agent.
The inter-machine hop is an operator-owned SSH tunnel; browser requests never
choose a host path, endpoint, import target, or command.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import hmac
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import math
from pathlib import Path, PurePosixPath
import re
from types import SimpleNamespace
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener


MAX_REQUEST_BYTES = 2 * 1024 * 1024
MAX_RESPONSE_BYTES = 32 * 1024 * 1024
_TOKEN = re.compile(r"[0-9a-f]{64}\Z")
_ID = re.compile(r"[0-9a-f]{32}\Z")
_CASE = re.compile(r"[A-Za-z_][A-Za-z0-9_]{0,79}\Z")
_CODE = re.compile(r"[a-z][a-z0-9_]{0,99}\Z")
_RUN_OPTIONS = {"parameters", "max_steps", "seed", "timeout_seconds"}
# Explicit method names and fields; there is no remote getattr surface.
_OPERATIONS = {
    "list_sources": ("store", set(), set()),
    "create_workspace": ("store", {"project_id"}, {"title"}),
    "list_workspaces": ("store", set(), set()),
    "get_workspace": ("store", {"workspace_id"}, set()),
    "get_revision": ("store", {"workspace_id"}, {"revision_id"}),
    "list_revisions": ("store", {"workspace_id"}, set()),
    "read_file": ("store", {"workspace_id", "revision_id", "path"}, set()),
    "save_files": ("store", {"workspace_id", "changes", "expected_revision"}, {"message"}),
    "parameter_schema": ("runner", {"workspace_id", "revision_id", "case_name"}, set()),
    "check": ("runner", {"workspace_id", "revision_id", "case_name"}, _RUN_OPTIONS),
    "submit": ("runner", {"workspace_id", "revision_id", "case_name", "request_id"}, _RUN_OPTIONS),
    "get_job": ("runner", {"workspace_id", "job_id"}, set()),
    "list_jobs": ("runner", {"workspace_id"}, set()),
}


class WorkspaceConnectionError(ValueError):
    def __init__(self, code: str, message: str):
        self.code = code
        super().__init__(message)


def _fail(code="invalid_workspace_request", message="工作区连接请求不符合契约。"):
    raise WorkspaceConnectionError(code, message)


def _finite(value):
    remaining = [value]
    while remaining:
        item = remaining.pop()
        if isinstance(item, float) and not math.isfinite(item):
            _fail()
        if isinstance(item, dict):
            remaining.extend(item.values())
        elif isinstance(item, list):
            remaining.extend(item)


def _loads(raw: bytes):
    def pairs(rows):
        value = {}
        for key, item in rows:
            if key in value:
                _fail()
            value[key] = item
        return value

    def constant(_value):
        _fail()

    try:
        value = json.loads(raw.decode("utf-8"), object_pairs_hook=pairs, parse_constant=constant)
        _finite(value)
        return value
    except (ValueError, UnicodeError, RecursionError):
        _fail()


def _token(value):
    if not isinstance(value, str) or not _TOKEN.fullmatch(value):
        _fail("workspace_connection_config_invalid", "工作区连接凭据配置无效。")
    return value


def _relative(value):
    if (not isinstance(value, str) or not value or len(value) > 400
            or any(c in value for c in ("\\", ":", "\x00"))):
        _fail()
    path = PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts or value != path.as_posix():
        _fail()


def _arguments(operation, value):
    if not isinstance(operation, str) or operation not in _OPERATIONS:
        _fail("workspace_operation_refused", "此操作不属于工作区连接接口。")
    _, required, optional = _OPERATIONS[operation]
    if not isinstance(value, dict) or required - value.keys() or value.keys() - required - optional:
        _fail()
    for name in ("workspace_id", "revision_id", "expected_revision", "request_id", "job_id"):
        if name in value:
            item = value[name]
            if name == "revision_id" and operation == "get_revision" and item is None:
                continue
            if not isinstance(item, str) or not _ID.fullmatch(item):
                _fail()
    if "project_id" in value:
        item = value["project_id"]
        if (not isinstance(item, str) or not 1 <= len(item) <= 240
                or any(ord(c) < 32 for c in item)):
            _fail()
    if "case_name" in value and (not isinstance(value["case_name"], str) or not _CASE.fullmatch(value["case_name"])):
        _fail()
    if "path" in value:
        _relative(value["path"])
    if "changes" in value:
        if not isinstance(value["changes"], dict) or not 1 <= len(value["changes"]) <= 1024:
            _fail()
        for path, content in value["changes"].items():
            _relative(path)
            if not isinstance(content, str):
                _fail()
    for name, maximum in (("title", 200), ("message", 1000)):
        if name in value and not (name == "title" and value[name] is None):
            if not isinstance(value[name], str) or len(value[name]) > maximum:
                _fail()
    if "parameters" in value and value["parameters"] is not None and not isinstance(value["parameters"], dict):
        _fail()
    if "max_steps" in value and (type(value["max_steps"]) is not int or not 1 <= value["max_steps"] <= 32):
        _fail()
    if "seed" in value and (type(value["seed"]) is not int or not 0 <= value["seed"] < 2**31):
        _fail()
    if "timeout_seconds" in value and (type(value["timeout_seconds"]) not in (int, float)
            or not math.isfinite(value["timeout_seconds"]) or not 5 <= value["timeout_seconds"] <= 180):
        _fail()
    _finite(value)
    return value


def _job_summaries(jobs):
    """History browsing transfers metadata; get_job retains the full evidence."""
    result = []
    for job in jobs:
        row = deepcopy(job)
        if isinstance(row.get("result"), dict):
            row["result"] = {name: item for name, item in row["result"].items()
                             if name in {"steps", "evaluations", "elapsed_seconds", "duration_seconds"}}
        row["result_is_summary"] = True
        result.append(row)
    return result


def _error_value(exc):
    if isinstance(exc, WorkspaceConnectionError):
        return {"code": exc.code, "message": str(exc)}
    # These imports execute only in the agent request handler, never in a
    # frontend importing or constructing the pure-stdlib client.
    from .lab_project_sources import ProjectSourceError
    from .lab_workspace_store import WorkspaceError
    from .lab_runner import TrialError

    if isinstance(exc, (ProjectSourceError, WorkspaceError, TrialError)):
        return {"code": exc.code, "message": str(exc)}
    if isinstance(exc, OSError):
        return {"code": "workspace_agent_storage_unavailable", "message": "本机工作区存储暂时不可用，记录未转交到服务器执行。"}
    return {"code": "workspace_agent_error", "message": "本机工作区未能完成请求，请检查本机连接器。"}


class WorkspaceAgentServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, address, *, token, store, runner):
        if (not isinstance(address, tuple) or len(address) != 2 or address[0] not in {"127.0.0.1", "localhost"}
                or type(address[1]) is not int or not 0 <= address[1] <= 65535):
            _fail("workspace_agent_address_refused", "工作区连接器只能监听本机回环地址。")
        self.token = _token(token)
        self.store, self.runner = store, runner
        super().__init__(("127.0.0.1", address[1]), _AgentHandler)


class _AgentHandler(BaseHTTPRequestHandler):
    server_version = "WorkspaceAgent"
    sys_version = ""

    def log_message(self, *_args):
        pass

    def setup(self):
        super().setup()
        self.connection.settimeout(10)

    def _reply(self, status, value):
        try:
            raw = json.dumps(value, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode("utf-8")
            if len(raw) > MAX_RESPONSE_BYTES:
                raise ValueError()
        except (ValueError, TypeError, UnicodeError, RecursionError):
            status = 500
            raw = b'{"ok":false,"error":{"code":"workspace_response_invalid","message":"Workspace response exceeds the transport contract."}}'
        try:
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(raw)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Connection", "close")
            self.end_headers()
            self.wfile.write(raw)
        except (OSError, TimeoutError):
            # A lost response must not trigger a second mutation or run.
            pass
        self.close_connection = True

    def do_GET(self):
        if self.path == "/health":
            self._reply(200, {"ok": True})
        else:
            self._reply(404, {"ok": False, "error": {"code": "workspace_endpoint_missing", "message": "Endpoint unavailable."}})

    def do_POST(self):
        supplied = self.headers.get_all("Authorization", [])
        expected = ("Bearer " + self.server.token).encode("ascii")
        if len(supplied) != 1 or not hmac.compare_digest(supplied[0].encode("utf-8"), expected):
            self._reply(401, {"ok": False, "error": {"code": "workspace_unauthorized", "message": "工作区连接认证失败。"}})
            return
        if self.path != "/rpc":
            self._reply(404, {"ok": False, "error": {"code": "workspace_endpoint_missing", "message": "Endpoint unavailable."}})
            return
        if self.headers.get("Origin") is not None:
            self._reply(403, {"ok": False, "error": {"code": "workspace_browser_rpc_refused", "message": "浏览器不直接调用本机连接器。"}})
            return
        try:
            lengths = self.headers.get_all("Content-Length", [])
            if (len(lengths) != 1 or not re.fullmatch(r"[0-9]{1,9}", lengths[0])
                    or not 1 <= int(lengths[0]) <= MAX_REQUEST_BYTES
                    or self.headers.get("Transfer-Encoding") is not None
                    or self.headers.get("Content-Type", "").split(";", 1)[0].strip().lower() != "application/json"):
                _fail()
            size = int(lengths[0])
            raw = self.rfile.read(size)
            if len(raw) != size:
                _fail()
            payload = _loads(raw)
            if not isinstance(payload, dict) or set(payload) != {"operation", "arguments"}:
                _fail()
            operation = payload["operation"]
            arguments = _arguments(operation, payload["arguments"])
            role = _OPERATIONS[operation][0]
            target = self.server.store if role == "store" else self.server.runner
            # The name was checked against the closed operation map above.
            result = getattr(target, operation)(**arguments)
            if operation == "list_jobs":
                result = _job_summaries(result)
            self._reply(200, {"ok": True, "result": result})
        except Exception as exc:
            error = _error_value(exc)
            status = 400 if isinstance(exc, WorkspaceConnectionError) else 409 if error["code"].endswith("conflict") else 422
            self._reply(status, {"ok": False, "error": error})


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *_args, **_kwargs):
        return None


def _endpoint(value):
    if (not isinstance(value, str) or not 1 <= len(value) <= 200 or value != value.strip()
            or any(ord(c) < 33 for c in value)):
        _fail("workspace_connection_config_invalid", "工作区连接地址配置无效。")
    try:
        parsed = urlsplit(value)
        port = parsed.port
    except ValueError:
        _fail("workspace_connection_config_invalid", "工作区连接地址配置无效。")
    if (parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "localhost"}
            or parsed.username is not None or parsed.password is not None
            or port is None or not 1 <= port <= 65535 or parsed.path not in {"", "/"}
            or parsed.query or parsed.fragment):
        _fail("workspace_connection_config_invalid", "工作区连接必须通过运营配置的本机回环隧道。")
    return f"http://{parsed.hostname}:{port}"


class WorkspaceRPCClient:
    def __init__(self, endpoint, token, *, timeout_seconds=30):
        self.endpoint = _endpoint(endpoint)
        self._token = _token(token)
        if (type(timeout_seconds) not in (int, float) or not math.isfinite(timeout_seconds)
                or not 1 <= timeout_seconds <= 120):
            _fail("workspace_connection_config_invalid", "工作区连接超时配置无效。")
        self.timeout_seconds = timeout_seconds
        self._opener = build_opener(ProxyHandler({}), _NoRedirect())

    def call(self, operation, arguments):
        _arguments(operation, arguments)
        try:
            raw = json.dumps({"operation": operation, "arguments": arguments}, ensure_ascii=False,
                             separators=(",", ":"), allow_nan=False).encode("utf-8")
        except (ValueError, TypeError, UnicodeError, RecursionError):
            _fail()
        if not 1 <= len(raw) <= MAX_REQUEST_BYTES:
            _fail("workspace_request_too_large", "本次修改超过连接请求大小，请分批保存。")
        request = Request(self.endpoint + "/rpc", data=raw, method="POST",
                          headers={"Authorization": "Bearer " + self._token, "Content-Type": "application/json"})
        try:
            try:
                response = self._opener.open(request, timeout=self.timeout_seconds)
            except HTTPError as exc:
                response = exc
            with response:
                advertised = response.headers.get("Content-Length")
                if advertised is not None and (not advertised.isdigit() or int(advertised) > MAX_RESPONSE_BYTES):
                    _fail("workspace_response_invalid", "本机工作区响应超出连接范围。")
                body = response.read(MAX_RESPONSE_BYTES + 1)
                status = response.status
        except WorkspaceConnectionError:
            raise
        except (OSError, URLError, TimeoutError):
            _fail("workspace_agent_offline", "本机连接不可用；请确认电脑和工作区连接器在线。服务器不会代为执行。")
        if len(body) > MAX_RESPONSE_BYTES:
            _fail("workspace_response_invalid", "本机工作区响应超出连接范围。")
        try:
            result = _loads(body)
        except WorkspaceConnectionError:
            _fail("workspace_response_invalid", "本机工作区没有返回有效响应。")
        if not isinstance(result, dict) or type(result.get("ok")) is not bool:
            _fail("workspace_response_invalid", "本机工作区没有返回有效响应。")
        if result["ok"]:
            if status != 200 or set(result) != {"ok", "result"}:
                _fail("workspace_response_invalid", "本机工作区响应与请求状态不一致。")
            return result["result"]
        error = result.get("error")
        if (set(result) != {"ok", "error"} or not isinstance(error, dict) or set(error) != {"code", "message"}
                or not isinstance(error.get("code"), str) or not _CODE.fullmatch(error["code"])
                or not isinstance(error.get("message"), str) or len(error["message"]) > 2000):
            _fail("workspace_response_invalid", "本机工作区没有返回有效诊断。")
        raise WorkspaceConnectionError(error["code"], error["message"])


class RemoteWorkspaceStore:
    def __init__(self, client):
        self._client = client
        identity = hashlib.sha256(client.endpoint.encode()).hexdigest()[:16]
        # UI cache identity only; no local source or storage directory is used.
        self.root = Path("/remote-project-workspace") / identity

    def list_sources(self):
        return self._client.call("list_sources", {})

    def create_workspace(self, project_id, *, title=None):
        return self._client.call("create_workspace", {"project_id": project_id, "title": title})

    def list_workspaces(self):
        return self._client.call("list_workspaces", {})

    def get_workspace(self, workspace_id):
        return self._client.call("get_workspace", {"workspace_id": workspace_id})

    def get_revision(self, workspace_id, revision_id=None):
        return self._client.call("get_revision", {"workspace_id": workspace_id, "revision_id": revision_id})

    def list_revisions(self, workspace_id):
        return self._client.call("list_revisions", {"workspace_id": workspace_id})

    def read_file(self, workspace_id, revision_id, path):
        return self._client.call("read_file", {"workspace_id": workspace_id, "revision_id": revision_id, "path": path})

    def save_files(self, workspace_id, changes, *, expected_revision, message=""):
        return self._client.call("save_files", {"workspace_id": workspace_id, "changes": changes,
                                               "expected_revision": expected_revision, "message": message})


class RemoteWorkspaceRunner:
    def __init__(self, client):
        self._client = client

    def parameter_schema(self, workspace_id, revision_id, case_name):
        return self._client.call("parameter_schema", {"workspace_id": workspace_id, "revision_id": revision_id, "case_name": case_name})

    def check(self, workspace_id, revision_id, case_name, *, parameters=None, max_steps=2, seed=42, timeout_seconds=60):
        return self._client.call("check", {"workspace_id": workspace_id, "revision_id": revision_id,
            "case_name": case_name, "parameters": parameters, "max_steps": max_steps, "seed": seed, "timeout_seconds": timeout_seconds})

    def submit(self, workspace_id, revision_id, case_name, *, parameters=None, max_steps=2, seed=42, timeout_seconds=60, request_id):
        return self._client.call("submit", {"workspace_id": workspace_id, "revision_id": revision_id,
            "case_name": case_name, "parameters": parameters, "max_steps": max_steps, "seed": seed,
            "timeout_seconds": timeout_seconds, "request_id": request_id})

    def get_job(self, workspace_id, job_id):
        return self._client.call("get_job", {"workspace_id": workspace_id, "job_id": job_id})

    def list_jobs(self, workspace_id):
        return self._client.call("list_jobs", {"workspace_id": workspace_id})


def _config(path):
    path = Path(path)
    try:
        if not path.is_file() or path.stat().st_size > 16 * 1024:
            raise ValueError()
        value = _loads(path.read_bytes())
    except (OSError, ValueError):
        _fail("workspace_connection_config_invalid", "工作区连接配置文件不可用。")
    if not isinstance(value, dict) or set(value) - {"endpoint", "token", "timeout_seconds"} or "token" not in value:
        _fail("workspace_connection_config_invalid", "工作区连接配置字段无效。")
    _token(value["token"])
    return value


def load_remote_runtime(config_path):
    config = _config(config_path)
    if "endpoint" not in config:
        _fail("workspace_connection_config_invalid", "工作区前端未配置固定连接地址。")
    client = WorkspaceRPCClient(config["endpoint"], config["token"],
                                timeout_seconds=config.get("timeout_seconds", 30))
    return SimpleNamespace(store=RemoteWorkspaceStore(client), runner=RemoteWorkspaceRunner(client), mode="remote")


def main(argv=None):
    parser = argparse.ArgumentParser(description="本机 Project 工作区连接器")
    commands = parser.add_subparsers(dest="command", required=True)
    serve = commands.add_parser("serve", help="监听本机回环地址，供认证隧道连接")
    serve.add_argument("--storage", type=Path, required=True)
    serve.add_argument("--project-root", action="append", default=[], metavar="NAME=PATH")
    serve.add_argument("--config", type=Path, required=True)
    serve.add_argument("--port", type=int, default=8640)
    args = parser.parse_args(argv)
    roots = {}
    for value in args.project_root:
        name, separator, path = value.partition("=")
        if not separator or not name or not path or name in roots:
            parser.error("--project-root 使用唯一的 NAME=PATH 格式。")
        roots[name] = path
    if not 1024 <= args.port <= 65535:
        parser.error("端口须为 1024 到 65535 的整数。")
    # Only the explicit agent process imports storage or execution components.
    from .lab_project_sources import ProjectSourceRegistry
    from .lab_workspace_store import WorkspaceStore
    from .lab_workspace_runner import WorkspaceRunner
    from .lab_workspace import _validate_storage

    config = _config(args.config)
    sources = ProjectSourceRegistry(roots or None)
    store = WorkspaceStore(_validate_storage(args.storage, sources), sources)
    runner = WorkspaceRunner(store)
    try:
        with WorkspaceAgentServer(("127.0.0.1", args.port), token=config["token"], store=store, runner=runner) as server:
            try:
                server.serve_forever(poll_interval=.5)
            except KeyboardInterrupt:
                pass
    finally:
        runner.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["WorkspaceConnectionError", "WorkspaceAgentServer", "WorkspaceRPCClient",
           "RemoteWorkspaceStore", "RemoteWorkspaceRunner", "load_remote_runtime", "main"]
