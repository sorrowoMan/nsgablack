"""Bounded trial jobs; algorithm execution stays in the standard Project runner.

The hosted Catalog never creates a local JobManager. A separate, credential-free
worker owns this queue. Jobs are ephemeral; downloading the Project/result is the
explicit persistence surface of the first workbench version.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import hashlib
import json
import re
import threading
import time
from typing import Callable, Mapping
import uuid

_ID = re.compile(r"[0-9a-f]{32}\Z")
MAX_RESULT_BYTES = 2 * 1024 * 1024


class LabJobError(ValueError):
    def __init__(self, code: str, message: str):
        self.code = code
        super().__init__(message)


def spec_digest(spec: Mapping) -> str:
    return hashlib.sha256(json.dumps(dict(spec), sort_keys=True, ensure_ascii=False,
                                    separators=(",", ":"), allow_nan=False).encode()).hexdigest()


class JobManager:
    def __init__(self, *, runner: Callable | None = None, max_pending: int = 3,
                 max_history: int = 16, ttl_seconds: int = 3600, project_sources=None):
        if not (1 <= max_pending <= 4 and max_pending <= max_history <= 32
                and 60 <= ttl_seconds <= 86400):
            raise ValueError("invalid_job_limits")
        self._runner = runner
        self._project_sources = project_sources
        self._max_pending = max_pending
        self._max_history = max_history
        self._ttl = ttl_seconds
        self._lock = threading.RLock()
        self._jobs: dict[str, dict] = {}
        self._requests: dict[str, str] = {}
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="lab-project")

    def _prune(self) -> None:
        completed = [(identity, item) for identity, item in self._jobs.items()
                     if item["status"] in {"succeeded", "failed"}]
        for identity, item in completed:
            expired = time.time() - item["finished_at"] > self._ttl
            if expired or len(self._jobs) >= self._max_history:
                del self._jobs[identity]
                self._requests.pop(item["request_id"], None)

    def submit(self, spec: Mapping, *, request_id: str) -> dict:
        from .lab_project import normalize_spec
        if not isinstance(request_id, str) or not _ID.fullmatch(request_id):
            raise LabJobError("invalid_request", "请求身份无效。")
        normalized = normalize_spec(spec)
        return self._submit_normalized(normalized, request_id=request_id, kind="assembly")

    def project_capabilities(self) -> dict:
        if self._project_sources is None:
            return {"enabled": False, "reason": "正式项目试跑尚未配置。"}
        return {"enabled": True, "schema": "nsgablack.project_trial/v1",
                **self._project_sources.search_projects(limit=50),
                "limits": {"parallel": 1, "threads": 1, "gpus": 0,
                           "timeout_seconds": 180}}

    def submit_project(self, spec: Mapping, *, request_id: str, confirmed_digest: str) -> dict:
        if not isinstance(request_id, str) or not _ID.fullmatch(request_id):
            raise LabJobError("invalid_request", "请求身份无效。")
        if self._project_sources is None:
            raise LabJobError("project_unavailable", "正式项目试跑尚未配置。")
        from .lab_project_trial import validate_project_proposal
        normalized = validate_project_proposal(self._project_sources, spec)
        if confirmed_digest != spec_digest(normalized):
            raise LabJobError("project_confirmation_mismatch", "请采用当前方案后再独立启动试跑。")
        return self._submit_normalized(normalized, request_id=request_id, kind="project")

    def _submit_normalized(self, normalized, *, request_id: str, kind: str) -> dict:
        digest = spec_digest(normalized)
        with self._lock:
            self._prune()
            previous = self._requests.get(request_id)
            if previous:
                job = self._jobs[previous]
                if job["spec_digest"] != digest:
                    raise LabJobError("request_conflict", "同一请求不能更换装配参数。")
                return self._public(job)
            pending = sum(j["status"] in {"queued", "running"} for j in self._jobs.values())
            if pending >= self._max_pending:
                raise LabJobError("queue_full", "试跑队列已满，请等待当前任务完成。")
            identity = uuid.uuid4().hex
            job = {"job_id": identity, "request_id": request_id, "status": "queued",
                   "spec": normalized, "spec_digest": digest, "created_at": time.time(),
                   "started_at": None, "finished_at": None, "result": None}
            if kind == "project":
                job["kind"] = kind
            self._jobs[identity] = job
            self._requests[request_id] = identity
            self._executor.submit(self._execute, identity)
            return self._public(job)

    @staticmethod
    def _public(job: dict) -> dict:
        return deepcopy({key: value for key, value in job.items() if key != "request_id"})

    def poll(self, job_id: str) -> dict:
        if not isinstance(job_id, str) or not _ID.fullmatch(job_id):
            raise LabJobError("invalid_job", "试跑身份无效。")
        with self._lock:
            self._prune()
            job = self._jobs.get(job_id)
            if job is None:
                raise LabJobError("job_missing", "试跑记录已过期或服务已重启，请重新试跑。")
            return self._public(job)

    def _execute(self, job_id: str) -> None:
        with self._lock:
            job = self._jobs[job_id]
            job.update(status="running", started_at=time.time())
            spec = deepcopy(job["spec"])
            kind = job.get("kind", "assembly")
        try:
            if kind == "project":
                from .lab_project_trial import run_project_trial
                result = run_project_trial(self._project_sources, spec,
                    confirmed_digest=spec_digest(spec), timeout_seconds=180)
            else:
                runner = self._runner
                if runner is None:
                    from .lab_runner import run_trial
                    runner = run_trial
                result = runner(spec, timeout_seconds=60)
            if (not isinstance(result, dict) or result.get("status") not in {"succeeded", "failed"}
                    or len(json.dumps(result, allow_nan=False).encode()) > MAX_RESULT_BYTES):
                raise ValueError("invalid_trial_result")
        except Exception:
            # Do not forward arbitrary exception text (paths, process env or keys).
            result = {"status": "failed", "error": {"code": "trial_worker_failed",
                      "message": "试跑进程未能交付有效结果，请检查配方与运行依赖。"}, "logs": ""}
        with self._lock:
            self._jobs[job_id].update(status=result["status"], result=result, finished_at=time.time())

    def close(self) -> None:
        self._executor.shutdown(wait=True, cancel_futures=False)
