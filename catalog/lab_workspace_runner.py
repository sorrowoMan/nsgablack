"""Persistent local revision jobs over the existing Project/Case trial runner.

This is a trusted local development surface, not a Python sandbox. Static
checks never import a Project. Explicit runs retain the existing Project L0,
bounded process execution, and verified result publication.
"""
from __future__ import annotations

import ast
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from copy import deepcopy
import json
import os
from pathlib import Path
import re
import sqlite3
import tempfile
import threading
import time
from uuid import uuid4

import psutil

from .lab_jobs import spec_digest
from .lab_project_sources import ProjectSourceError, ProjectSourceRegistry
from .lab_project_trial import (TrialError, project_parameter_schema,
                                run_project_trial, validate_project_proposal)
from .lab_workspace_store import WorkspaceError


_ID = re.compile(r"[0-9a-f]{32}\Z")
_ACTIVE = {"queued", "running"}
_TERMINAL = {"succeeded", "failed", "interrupted"}
_RUNTIMES: dict[str, "_Runtime"] = {}
_RUNTIME_LOCK = threading.RLock()


def _fail(code, message):
    raise WorkspaceError(code, message)


def _identity(value, label):
    if not isinstance(value, str) or not _ID.fullmatch(value):
        _fail("invalid_workspace_job", f"{label}身份无效。")
    return value


def _json(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False,
                      separators=(",", ":"), allow_nan=False)


def _owner_alive(owner):
    try:
        process = psutil.Process(owner["pid"])
        return process.is_running() and abs(process.create_time() - owner["process_created"]) < 0.01
    except (psutil.Error, KeyError, TypeError, ValueError):
        return False


class _Database:
    def __init__(self, root):
        self.path = root / "workspace-jobs.sqlite3"
        with self.connect() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS workspace_jobs (
                    job_id TEXT PRIMARY KEY, workspace_id TEXT NOT NULL,
                    request_id TEXT NOT NULL, fingerprint TEXT NOT NULL,
                    status TEXT NOT NULL, created_at REAL NOT NULL,
                    record TEXT NOT NULL, UNIQUE(workspace_id, request_id)
                );
                CREATE TABLE IF NOT EXISTS workspace_runner_owner (
                    singleton INTEGER PRIMARY KEY CHECK(singleton=1), record TEXT NOT NULL
                );
            """)
        self.recover_abandoned()

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        try:
            with db:
                yield db
        finally:
            db.close()

    @staticmethod
    def _interrupt(db):
        for row in db.execute("SELECT job_id,record FROM workspace_jobs WHERE status IN ('queued','running')").fetchall():
            value = json.loads(row["record"])
            value.update(status="interrupted", finished_at=time.time(), error={
                "code": "workspace_runner_interrupted",
                "message": "上次本机运行进程已结束；此任务保留为中断记录，不自动重跑。"})
            db.execute("UPDATE workspace_jobs SET status='interrupted',record=? WHERE job_id=?",
                       (_json(value), row["job_id"]))

    def recover_abandoned(self):
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT record FROM workspace_runner_owner WHERE singleton=1").fetchone()
            if row is None or not _owner_alive(json.loads(row["record"])):
                self._interrupt(db)
                db.execute("DELETE FROM workspace_runner_owner WHERE singleton=1")

    def claim(self, identity):
        owner = {"id": identity, "pid": os.getpid(),
                 "process_created": psutil.Process().create_time()}
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT record FROM workspace_runner_owner WHERE singleton=1").fetchone()
            if row is not None and _owner_alive(json.loads(row["record"])):
                _fail("workspace_runner_busy", "此存储已有本机运行器；可查看历史，请在原工作区提交运行。")
            self._interrupt(db)
            db.execute("INSERT OR REPLACE INTO workspace_runner_owner VALUES (1,?)", (_json(owner),))

    def release(self, identity):
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT record FROM workspace_runner_owner WHERE singleton=1").fetchone()
            if row and json.loads(row["record"])["id"] == identity:
                db.execute("DELETE FROM workspace_runner_owner WHERE singleton=1")

    def by_request(self, workspace_id, request_id):
        with self.connect() as db:
            row = db.execute("SELECT record FROM workspace_jobs WHERE workspace_id=? AND request_id=?",
                             (workspace_id, request_id)).fetchone()
        return None if row is None else json.loads(row["record"])

    def insert(self, value):
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            prior = db.execute("SELECT record FROM workspace_jobs WHERE workspace_id=? AND request_id=?",
                               (value["workspace_id"], value["request_id"])).fetchone()
            if prior:
                return json.loads(prior["record"])
            count = db.execute("SELECT COUNT(*) FROM workspace_jobs WHERE status IN ('queued','running')").fetchone()[0]
            if count >= 3:
                _fail("workspace_queue_full", "本机运行队列已满，请等待现有任务完成。")
            db.execute("INSERT INTO workspace_jobs VALUES (?,?,?,?,?,?,?)", (
                value["job_id"], value["workspace_id"], value["request_id"], value["fingerprint"],
                value["status"], value["created_at"], _json(value)))
            return value

    def claim_next(self):
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT record FROM workspace_jobs WHERE status='queued' ORDER BY created_at,job_id LIMIT 1").fetchone()
            if row is None:
                return None
            value = json.loads(row["record"])
            value.update(status="running", started_at=time.time())
            db.execute("UPDATE workspace_jobs SET status='running',record=? WHERE job_id=?", (_json(value), value["job_id"]))
            return value

    def finish(self, value):
        with self.connect() as db:
            db.execute("UPDATE workspace_jobs SET status=?,record=? WHERE job_id=? AND status='running'",
                       (value["status"], _json(value), value["job_id"]))


class _Runtime:
    def __init__(self, runner):
        self.runner = runner
        self.identity = uuid4().hex
        self.runner._db.claim(self.identity)
        self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="workspace-project")
        self.lock = threading.RLock()
        self.scheduled = False
        self.closed = False

    def kick(self):
        with self.lock:
            if self.closed:
                _fail("workspace_runner_closed", "本机运行器已关闭。")
            if not self.scheduled:
                self.scheduled = True
                self.executor.submit(self._drain)

    def _drain(self):
        try:
            while True:
                value = self.runner._db.claim_next()
                if value is None:
                    return
                self.runner._execute(value)
        finally:
            with self.lock:
                self.scheduled = False
                # A submit may have committed between claim_next and this lock.
                with self.runner._db.connect() as db:
                    pending = db.execute("SELECT 1 FROM workspace_jobs WHERE status='queued' LIMIT 1").fetchone()
                if pending and not self.closed:
                    self.kick()

    def close(self):
        with self.lock:
            self.closed = True
        self.executor.shutdown(wait=True)
        self.runner._db.release(self.identity)


class WorkspaceRunner:
    """One local queue with persistent jobs, frozen revisions and explicit runs."""

    def __init__(self, store):
        self.store = store
        self.root = Path(store.root).resolve()
        self._db = _Database(self.root)
        self._key = str(self.root)
        self._closed = False

    @contextmanager
    def _frozen(self, workspace_id, revision_id):
        self.store.get_workspace(workspace_id)
        revision = self.store.get_revision(workspace_id, revision_id)
        base = self.root / "workspace-checks"
        base.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="revision-", dir=base) as folder:
            project = self.store.materialize(workspace_id, revision["revision_id"], Path(folder) / "project")
            sources = ProjectSourceRegistry({"revision": project})
            manifest = sources.snapshot_manifest("revision:.")
            if manifest["source_digest"] != revision["source_digest"] or manifest["files"] != revision["files"]:
                _fail("workspace_revision_mismatch", "冻结副本与保存的修订闭包不一致，未执行。")
            yield revision, sources

    def parameter_schema(self, workspace_id, revision_id, case_name):
        with self._frozen(workspace_id, revision_id) as (revision, sources):
            schema = project_parameter_schema(sources, "revision:.", case_name, allow_parameterless=True)
            return {**schema, "workspace_id": workspace_id, "revision_id": revision["revision_id"],
                    "source_digest": revision["source_digest"]}

    @staticmethod
    def _proposal(revision, case_name, parameters, max_steps, seed, timeout_seconds):
        return {"schema": "nsgablack.project_trial/v1", "project_id": "revision:.",
                "project_revision": revision["source_digest"], "case_name": case_name,
                "parameters": {} if parameters is None else parameters,
                "budget": {"max_steps": max_steps, "timeout_seconds": timeout_seconds,
                           "threads": 1, "gpus": 0}, "seed": seed}

    def check(self, workspace_id, revision_id, case_name, *, parameters=None,
              max_steps=2, seed=42, timeout_seconds=60):
        revision = self.store.get_revision(workspace_id, revision_id)
        report = {"ok": False, "workspace_id": workspace_id, "revision_id": revision["revision_id"],
                  "source_digest": revision["source_digest"], "diagnostics": [],
                  "scope": "frozen_revision_static_only", "builder_executed": False,
                  "algorithm_executed": False, "checked_python_files": 0}
        try:
            with self._frozen(workspace_id, revision["revision_id"]) as (_, sources):
                project = sources.resolve_project("revision:.")
                for row in revision["files"]:
                    if not row["path"].endswith(".py"):
                        continue
                    report["checked_python_files"] += 1
                    try:
                        ast.parse((project / row["path"]).read_bytes(), filename=row["path"])
                    except (SyntaxError, UnicodeError) as exc:
                        report["diagnostics"].append({"code": "workspace_python_syntax",
                            "message": getattr(exc, "msg", "Python源文件编码无效。"),
                            "path": row["path"], "line": getattr(exc, "lineno", None)})
                schema = project_parameter_schema(sources, "revision:.", case_name, allow_parameterless=True)
                report["parameter_schema"] = schema
                offered = self._proposal(revision, case_name, parameters, max_steps, seed, timeout_seconds)
                report["proposal"] = validate_project_proposal(sources, offered, allow_parameterless=True)
                report["ok"] = not report["diagnostics"]
        except (WorkspaceError, ProjectSourceError, TrialError) as exc:
            report["diagnostics"].append({"code": exc.code, "message": str(exc)})
        return report

    def _runtime(self):
        if self._closed:
            _fail("workspace_runner_closed", "本机运行器已关闭。")
        with _RUNTIME_LOCK:
            runtime = _RUNTIMES.get(self._key)
            if runtime is None or runtime.closed:
                runtime = _Runtime(self)
                _RUNTIMES[self._key] = runtime
            return runtime

    @staticmethod
    def _public(value):
        return deepcopy({key: item for key, item in value.items()
                         if key not in {"request_id", "fingerprint"}})

    def submit(self, workspace_id, revision_id, case_name, *, parameters=None,
               max_steps=2, seed=42, timeout_seconds=60, request_id):
        _identity(request_id, "请求")
        revision = self.store.get_revision(workspace_id, revision_id)
        offered = self._proposal(revision, case_name, parameters, max_steps, seed, timeout_seconds)
        fingerprint = spec_digest({"workspace_id": workspace_id, "revision_id": revision["revision_id"],
                                   "proposal": offered})
        existing = self._db.by_request(workspace_id, request_id)
        if existing:
            if existing["fingerprint"] != fingerprint:
                _fail("workspace_request_conflict", "同一运行请求不能更换修订、参数或预算。")
            return self._public(existing)
        checked = self.check(workspace_id, revision["revision_id"], case_name, parameters=parameters,
                             max_steps=max_steps, seed=seed, timeout_seconds=timeout_seconds)
        if not checked["ok"]:
            _fail("workspace_static_check_failed", "静态校验未通过；请先查看并修正本修订的诊断。")
        runtime = self._runtime()
        value = {"job_id": uuid4().hex, "request_id": request_id, "fingerprint": fingerprint,
                 "workspace_id": workspace_id, "revision_id": revision["revision_id"],
                 "source_digest": revision["source_digest"], "case_name": case_name,
                 "status": "queued", "created_at": time.time(), "started_at": None,
                 "finished_at": None, "proposal": checked["proposal"], "result": None, "error": None}
        saved = self._db.insert(value)
        if saved["fingerprint"] != fingerprint:
            _fail("workspace_request_conflict", "同一运行请求不能更换修订、参数或预算。")
        runtime.kick()
        return self._public(saved)

    def _execute(self, value):
        try:
            with self._frozen(value["workspace_id"], value["revision_id"]) as (_, sources):
                result = run_project_trial(sources, value["proposal"],
                    confirmed_digest=spec_digest(value["proposal"]),
                    workspace_root=self.root / "workspace-runs" / value["job_id"],
                    allow_parameterless=True)
            value.update(status="succeeded" if result.get("success") is True else "failed",
                         result=result, error=result.get("error"))
        except (WorkspaceError, ProjectSourceError, TrialError) as exc:
            value.update(status="failed", error={"code": exc.code, "message": str(exc)})
        except Exception:
            value.update(status="failed", error={"code": "workspace_run_failed",
                "message": "本机工作区运行未能完成；修订和任务记录已保留。"})
        value["finished_at"] = time.time()
        self._db.finish(value)

    def get_job(self, workspace_id, job_id):
        self.store.get_workspace(workspace_id)
        _identity(job_id, "任务")
        with self._db.connect() as db:
            row = db.execute("SELECT record FROM workspace_jobs WHERE workspace_id=? AND job_id=?",
                             (workspace_id, job_id)).fetchone()
        if row is None:
            _fail("workspace_job_missing", "此工作区没有对应的运行记录。")
        return self._public(json.loads(row["record"]))

    def list_jobs(self, workspace_id):
        self.store.get_workspace(workspace_id)
        with self._db.connect() as db:
            rows = db.execute("SELECT record FROM workspace_jobs WHERE workspace_id=? ORDER BY created_at DESC,job_id DESC",
                              (workspace_id,)).fetchall()
        return [self._public(json.loads(row["record"])) for row in rows]

    def close(self):
        with _RUNTIME_LOCK:
            runtime = _RUNTIMES.get(self._key)
            if runtime is not None:
                runtime.close()
                _RUNTIMES.pop(self._key, None)
        self._closed = True


__all__ = ["WorkspaceRunner"]
