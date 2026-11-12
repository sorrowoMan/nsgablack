"""Private transports for bounded Project trials or assembly drafts.

Run in a separate network-restricted container with a read-only source image.
This HTTP transport delegates to the existing Project runner, not a scheduler
for cross-Case execution. Project L0 remains the resource authority. Runner and
assistant roles are separate processes with independent grants; only the
assistant loads a model configuration, and it never executes a draft.
"""
from __future__ import annotations

import argparse
import hmac
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import re

from .lab_jobs import JobManager, LabJobError


class LabHTTPServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, address, *, token: str, jobs=None, role: str = "runner",
                 project_sources=None, result_token: str | None = None):
        if not re.fullmatch(r"[a-f0-9]{64}", token):
            raise ValueError("invalid_worker_token")
        self.token = token
        if result_token is not None and (not re.fullmatch(r"[a-f0-9]{64}", result_token)
                                         or result_token == token):
            raise ValueError("invalid_result_token")
        self.result_token = result_token
        if role not in {"runner", "assistant"} or role == "assistant" and jobs is None:
            raise ValueError("invalid_worker_role")
        self.role = role
        self.jobs = jobs if jobs is not None else JobManager(project_sources=project_sources)
        super().__init__(address, LabRequestHandler)

    def server_close(self):
        super().server_close()
        self.jobs.close()


class LabRequestHandler(BaseHTTPRequestHandler):
    server_version = "LabWorker"

    def log_message(self, *_args):
        pass

    def setup(self):
        super().setup()
        self.connection.settimeout(10)

    def _reply(self, status: int, value: dict):
        data = json.dumps(value, ensure_ascii=False, allow_nan=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(data)

    def _authorized(self, *, result_reader=False):
        supplied = self.headers.get("Authorization", "").encode("utf-8")
        authorized = hmac.compare_digest(supplied, ("Bearer " + self.server.token).encode("ascii"))
        if result_reader and self.server.result_token:
            authorized = authorized or hmac.compare_digest(supplied,
                ("Bearer " + self.server.result_token).encode("ascii"))
        if not authorized:
            self._reply(401, {"error": {"code": "unauthorized"}})
            return False
        return True

    def do_GET(self):
        if self.path == "/health":
            self._reply(200, {"ok": True})
            return
        project_result = re.fullmatch(r"/project/jobs/[0-9a-f]{32}", self.path)
        if not self._authorized(result_reader=bool(project_result)):
            return
        if self.path == "/project/capabilities":
            capabilities = getattr(self.server.jobs, "project_capabilities", None)
            self._reply(200, capabilities() if capabilities else {"enabled": False})
        elif project_result:
            try:
                job = self.server.jobs.poll(self.path.rsplit("/", 1)[1])
                if self.server.role == "runner" and job.get("kind") != "project":
                    raise LabJobError("job_missing", "项目试跑不存在。")
                self._reply(200, job)
            except LabJobError as exc:
                self._reply(404, {"error": {"code": exc.code}})
        elif self.path == "/capabilities":
            from .lab_assembly import assembly_catalog
            if self.server.role == "assistant":
                self._reply(200, {"schema": "nsgablack.lab.assistant_capabilities/v1",
                                  "assembly_catalog": assembly_catalog(),
                                  **self.server.jobs.capabilities()})
                return
            from .lab_project import list_recipes
            self._reply(200, {"schema": "nsgablack.lab.capabilities/v1", "recipes": list(list_recipes()),
                              "assembly_catalog": assembly_catalog(),
                              "limits": {"timeout_seconds": 60, "parallel": 1,
                                         "max_pending": 3, "history_seconds": 3600}})
        elif re.fullmatch(r"/jobs/[0-9a-f]{32}", self.path):
            try:
                self._reply(200, self.server.jobs.poll(self.path.rsplit("/", 1)[1]))
            except LabJobError as exc:
                self._reply(404, {"error": {"code": exc.code}})
        else:
            self._reply(404, {"error": {"code": "unknown_endpoint"}})

    def do_POST(self):
        if not self._authorized():
            return
        if self.path not in {"/jobs", "/project/jobs"}:
            self._reply(404, {"error": {"code": "unknown_endpoint"}})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            limit = 65536 if self.server.role == "assistant" else 32768
            if not 1 <= length <= limit or self.headers.get("Transfer-Encoding"):
                raise ValueError()
            value = json.loads(self.rfile.read(length))
            if self.path == "/project/jobs":
                if self.server.role == "assistant":
                    required = {"request_id", "project_id", "instruction"}
                    optional = {"history", "proposal", "trial"}
                    if not isinstance(value, dict) or required - set(value) or set(value) - required - optional:
                        raise ValueError()
                    result = self.server.jobs.submit_project(
                        {key: item for key, item in value.items() if key != "request_id"},
                        request_id=value["request_id"])
                else:
                    if not isinstance(value, dict) or set(value) != {"request_id", "spec", "confirmed_digest"}:
                        raise ValueError()
                    result = self.server.jobs.submit_project(value["spec"], request_id=value["request_id"],
                                                           confirmed_digest=value["confirmed_digest"])
                self._reply(202, result)
                return
            fields = {"request_id", "spec"}
            if self.server.role == "assistant":
                fields.add("instruction")
            optional = {"guide_context"} if self.server.role == "assistant" else set()
            if not isinstance(value, dict) or set(value) - (fields | optional) or fields - set(value):
                raise ValueError()
            kwargs = {"request_id": value["request_id"]}
            if self.server.role == "assistant":
                kwargs["instruction"] = value["instruction"]
                if "guide_context" in value:
                    kwargs["guide_context"] = value["guide_context"]
            result = self.server.jobs.submit(value["spec"], **kwargs)
            self._reply(202, result)
        except LabJobError as exc:
            status = 429 if exc.code in {"queue_full", "budget_exhausted"} else 409 if exc.code == "request_conflict" else 400
            self._reply(status, {"error": {"code": exc.code}})
        except (ValueError, TypeError, UnicodeError, KeyError):
            self._reply(400, {"error": {"code": "invalid_spec"}})


def main(argv=None):
    parser = argparse.ArgumentParser(description="Private Catalog trial worker")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8622)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--role", choices=("runner", "assistant"), default="runner")
    parser.add_argument("--ai-config", type=Path)
    parser.add_argument("--state-path", type=Path)
    parser.add_argument("--project-root", action="append", type=Path,
                        help="Operator-owned roots of trusted formal Projects")
    args = parser.parse_args(argv)
    if not args.config.is_file() or args.config.stat().st_size > 4096:
        parser.error("worker config is missing or oversized")
    config = json.loads(args.config.read_text(encoding="utf-8"))
    if not isinstance(config, dict) or "token" not in config or set(config) - {"token", "result_token"}:
        parser.error("worker config requires token and optional read-only result_token")
    from .lab_project_sources import ProjectSourceRegistry
    roots = {f"workspace{i}": path for i, path in enumerate(args.project_root)} if args.project_root else None
    project_sources = ProjectSourceRegistry(roots)
    jobs = None
    if args.role == "assistant":
        if args.ai_config is None or args.state_path is None:
            parser.error("assistant requires an isolated AI config and reservation state")
        from .lab_assistant import AssistantManager
        from .lab_model_provider import create_assistant_generator, load_assistant_model_config
        from .lab_project_assistant import ProjectAssistantRuntime
        from .lab_client import project_result_reader
        runtime = ProjectAssistantRuntime(project_sources, trial_reader=project_result_reader())
        jobs = AssistantManager(create_assistant_generator(load_assistant_model_config(args.ai_config)),
                                state_path=args.state_path, project_runtime=runtime)
    elif args.ai_config is not None or args.state_path is not None:
        parser.error("runner cannot receive AI config or reservation state")
    with LabHTTPServer((args.host, args.port), token=config["token"], jobs=jobs, role=args.role,
                       project_sources=project_sources, result_token=config.get("result_token")) as server:
        server.serve_forever()


if __name__ == "__main__":
    main()
