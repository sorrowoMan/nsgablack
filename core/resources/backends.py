"""Backend protocols for the L0 task/resource runtime plane."""

from __future__ import annotations

import json
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from threading import Condition, RLock
from typing import Any, Dict, Mapping, Optional, Sequence
from uuid import uuid4

from blackbase.resources import ClaimedTask, RedisTaskTransport, ResourceOffer

from .model import DataRef, TaskEnvelope, TaskResult, WorkerDescriptor


TASK_ENVELOPE_SCHEMA = "nsgablack.l0.task_envelope.v1"
TASK_RESULT_SCHEMA = "nsgablack.l0.task_result.v1"


def infer_task_run_id(task: TaskEnvelope) -> str:
    payload = dict(task.payload or {})
    return str(payload.get("run_id") or task.namespace or "default")


def infer_result_run_id(result: TaskResult) -> str:
    metadata = dict(result.metadata or {})
    run_id = metadata.get("run_id")
    if run_id:
        return str(run_id)
    resource_context = dict(result.resource_context or {})
    run_id = resource_context.get("run_id")
    if run_id:
        return str(run_id)
    raise ValueError("TaskResult metadata or resource_context must include run_id")


def task_to_json(task: TaskEnvelope) -> str:
    return json.dumps(
        {"schema": TASK_ENVELOPE_SCHEMA, "task": task.as_dict()},
        ensure_ascii=False,
        separators=(",", ":"),
    )


def task_from_json(raw: Any) -> TaskEnvelope:
    if isinstance(raw, bytes):
        raw = raw.decode("utf-8")
    data = json.loads(str(raw))
    if str(data.get("schema", "")) != TASK_ENVELOPE_SCHEMA:
        raise ValueError("unsupported L0 task envelope schema")
    if "task" not in data:
        raise ValueError("L0 task payload must contain key 'task'")
    return TaskEnvelope.from_dict(dict(data["task"]))


def result_to_json(result: TaskResult) -> str:
    return json.dumps(
        {"schema": TASK_RESULT_SCHEMA, "result": result.as_dict()},
        ensure_ascii=False,
        separators=(",", ":"),
    )


def result_from_json(raw: Any) -> TaskResult:
    if isinstance(raw, bytes):
        raw = raw.decode("utf-8")
    data = json.loads(str(raw))
    if str(data.get("schema", "")) != TASK_RESULT_SCHEMA:
        raise ValueError("unsupported L0 task result schema")
    if "result" not in data:
        raise ValueError("L0 result payload must contain key 'result'")
    return TaskResult.from_dict(dict(data["result"]))


class TaskQueueBackend(ABC):
    """Queue backend for TaskEnvelope packets."""

    @abstractmethod
    def submit(self, task: TaskEnvelope) -> None:
        raise NotImplementedError

    def submit_many(self, tasks: Sequence[TaskEnvelope]) -> None:
        for task in tuple(tasks):
            self.submit(task)

    @abstractmethod
    def claim(self, run_id: Optional[str] = None, *, timeout_seconds: int = 1) -> Optional[TaskEnvelope]:
        raise NotImplementedError


class TaskResultBackend(ABC):
    """Result storage backend for TaskResult packets."""

    @abstractmethod
    def complete(self, result: TaskResult) -> None:
        raise NotImplementedError

    @abstractmethod
    def get_result(self, run_id: str, task_id: str) -> Optional[TaskResult]:
        raise NotImplementedError


class TaskStateBackend(ABC):
    """Small task status storage backend."""

    @abstractmethod
    def set_task_state(
        self,
        task_id: str,
        state: Mapping[str, Any],
        *,
        ttl_seconds: Optional[float] = None,
    ) -> None:
        raise NotImplementedError

    @abstractmethod
    def get_task_state(self, task_id: str) -> Optional[Dict[str, Any]]:
        raise NotImplementedError

    @abstractmethod
    def delete_task_state(self, task_id: str) -> None:
        raise NotImplementedError


class ArtifactBackend(ABC):
    """Large payload storage backend."""

    @abstractmethod
    def put_bytes(
        self,
        name: str,
        data: bytes,
        *,
        kind: str = "artifact",
        media_type: str = "application/octet-stream",
        metadata: Optional[Mapping[str, Any]] = None,
    ) -> DataRef:
        raise NotImplementedError

    @abstractmethod
    def get_bytes(self, ref: DataRef | Mapping[str, Any] | str) -> bytes:
        raise NotImplementedError

    def put_json(
        self,
        name: str,
        payload: Mapping[str, Any],
        *,
        kind: str = "artifact",
        metadata: Optional[Mapping[str, Any]] = None,
    ) -> DataRef:
        raw = json.dumps(dict(payload), ensure_ascii=False, sort_keys=True).encode("utf-8")
        return self.put_bytes(name, raw, kind=kind, media_type="application/json", metadata=metadata)

    def get_json(self, ref: DataRef | Mapping[str, Any] | str) -> Dict[str, Any]:
        data = json.loads(self.get_bytes(ref).decode("utf-8"))
        return dict(data) if isinstance(data, Mapping) else {}


class DataTransportBackend(ABC):
    """Data movement backend for task payloads and artifact references."""

    @abstractmethod
    def send(self, value: Any, *, kind: str = "payload") -> Any:
        raise NotImplementedError

    @abstractmethod
    def receive(self, value: Any) -> Any:
        raise NotImplementedError


class WorkerRegistryBackend(ABC):
    """Worker registration and heartbeat backend."""

    @abstractmethod
    def register(self, worker: WorkerDescriptor | Mapping[str, Any], *, ttl_seconds: Optional[float] = None) -> None:
        raise NotImplementedError

    @abstractmethod
    def heartbeat(
        self,
        worker_id: str,
        payload: Optional[Mapping[str, Any]] = None,
        *,
        ttl_seconds: int = 30,
    ) -> None:
        raise NotImplementedError

    @abstractmethod
    def get_worker(self, worker_id: str) -> Optional[WorkerDescriptor]:
        raise NotImplementedError


class InMemoryTaskQueueBackend(TaskQueueBackend):
    def __init__(self, *, namespace: str = "nsgablack:l0", queue_scope: str = "global") -> None:
        self.namespace = _normalize_namespace(namespace)
        self.queue_scope = _normalize_queue_scope(queue_scope)
        self._queues: Dict[str, list[str]] = {}
        self._cond = Condition()

    def task_queue_key(self, run_id: Optional[str] = None) -> str:
        return _task_queue_key(self.namespace, self.queue_scope, run_id)

    def submit(self, task: TaskEnvelope) -> None:
        raw = task_to_json(task)
        key = self.task_queue_key(infer_task_run_id(task))
        with self._cond:
            self._queues.setdefault(key, []).append(raw)
            self._cond.notify_all()

    def submit_many(self, tasks: Sequence[TaskEnvelope]) -> None:
        with self._cond:
            for task in tuple(tasks):
                key = self.task_queue_key(infer_task_run_id(task))
                self._queues.setdefault(key, []).append(task_to_json(task))
            self._cond.notify_all()

    def claim(self, run_id: Optional[str] = None, *, timeout_seconds: int = 1) -> Optional[TaskEnvelope]:
        key = self.task_queue_key(run_id)
        deadline = time.time() + max(0.0, float(timeout_seconds))
        with self._cond:
            while True:
                queue = self._queues.get(key, [])
                if queue:
                    return task_from_json(queue.pop(0))
                remaining = deadline - time.time()
                if remaining <= 0:
                    return None
                self._cond.wait(timeout=min(remaining, 0.05))


class InMemoryTaskResultBackend(TaskResultBackend):
    def __init__(self, *, namespace: str = "nsgablack:l0") -> None:
        self.namespace = _normalize_namespace(namespace)
        self._results: Dict[str, str] = {}
        self._lock = RLock()

    def result_key(self, run_id: str, task_id: str) -> str:
        return _result_key(self.namespace, run_id, task_id)

    def complete(self, result: TaskResult) -> None:
        with self._lock:
            self._results[self.result_key(infer_result_run_id(result), result.task_id)] = result_to_json(result)

    def get_result(self, run_id: str, task_id: str) -> Optional[TaskResult]:
        with self._lock:
            raw = self._results.get(self.result_key(run_id, task_id))
        return None if raw is None else result_from_json(raw)


class InMemoryTaskStateBackend(TaskStateBackend):
    def __init__(self) -> None:
        self._states: Dict[str, Dict[str, Any]] = {}
        self._expires_at: Dict[str, float] = {}
        self._lock = RLock()

    def set_task_state(
        self,
        task_id: str,
        state: Mapping[str, Any],
        *,
        ttl_seconds: Optional[float] = None,
    ) -> None:
        with self._lock:
            self._sweep_locked()
            self._states[str(task_id)] = dict(state)
            if ttl_seconds is not None and float(ttl_seconds) > 0:
                self._expires_at[str(task_id)] = time.time() + float(ttl_seconds)
            else:
                self._expires_at.pop(str(task_id), None)

    def get_task_state(self, task_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            self._sweep_locked()
            value = self._states.get(str(task_id))
            return None if value is None else dict(value)

    def delete_task_state(self, task_id: str) -> None:
        with self._lock:
            self._states.pop(str(task_id), None)
            self._expires_at.pop(str(task_id), None)

    def _sweep_locked(self) -> None:
        now = time.time()
        expired = [key for key, until in self._expires_at.items() if float(until) <= now]
        for key in expired:
            self._expires_at.pop(key, None)
            self._states.pop(key, None)


class InMemoryWorkerRegistryBackend(WorkerRegistryBackend):
    def __init__(self) -> None:
        self._workers: Dict[str, WorkerDescriptor] = {}
        self._heartbeats: Dict[str, Dict[str, Any]] = {}
        self._worker_expires_at: Dict[str, float] = {}
        self._heartbeat_expires_at: Dict[str, float] = {}
        self._lock = RLock()

    def register(self, worker: WorkerDescriptor | Mapping[str, Any], *, ttl_seconds: Optional[float] = None) -> None:
        item = worker if isinstance(worker, WorkerDescriptor) else WorkerDescriptor.from_dict(worker)
        with self._lock:
            self._sweep_locked()
            self._workers[str(item.worker_id)] = item
            if ttl_seconds is not None and float(ttl_seconds) > 0:
                self._worker_expires_at[str(item.worker_id)] = time.time() + float(ttl_seconds)

    def heartbeat(
        self,
        worker_id: str,
        payload: Optional[Mapping[str, Any]] = None,
        *,
        ttl_seconds: int = 30,
    ) -> None:
        key = str(worker_id)
        with self._lock:
            self._sweep_locked()
            self._heartbeats[key] = {"worker_id": key, "time": time.time(), "payload": dict(payload or {})}
            if int(ttl_seconds) > 0:
                self._heartbeat_expires_at[key] = time.time() + int(ttl_seconds)

    def get_worker(self, worker_id: str) -> Optional[WorkerDescriptor]:
        with self._lock:
            self._sweep_locked()
            return self._workers.get(str(worker_id))

    def get_heartbeat(self, worker_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            self._sweep_locked()
            payload = self._heartbeats.get(str(worker_id))
            return None if payload is None else dict(payload)

    def _sweep_locked(self) -> None:
        now = time.time()
        expired_workers = [key for key, until in self._worker_expires_at.items() if float(until) <= now]
        for key in expired_workers:
            self._worker_expires_at.pop(key, None)
            self._workers.pop(key, None)
        expired_heartbeats = [key for key, until in self._heartbeat_expires_at.items() if float(until) <= now]
        for key in expired_heartbeats:
            self._heartbeat_expires_at.pop(key, None)
            self._heartbeats.pop(key, None)


class InMemoryArtifactBackend(ArtifactBackend):
    def __init__(self, *, backend_name: str = "memory") -> None:
        self.backend_name = str(backend_name or "memory")
        self._data: Dict[str, bytes] = {}
        self._lock = RLock()

    def put_bytes(
        self,
        name: str,
        data: bytes,
        *,
        kind: str = "artifact",
        media_type: str = "application/octet-stream",
        metadata: Optional[Mapping[str, Any]] = None,
    ) -> DataRef:
        key = str(name).strip().replace("\\", "/").lstrip("/") or f"artifact_{int(time.time() * 1000)}"
        with self._lock:
            self._data[key] = bytes(data)
        return DataRef(
            uri=key,
            kind=kind,
            backend=self.backend_name,
            media_type=media_type,
            size_bytes=len(data),
            metadata=dict(metadata or {}),
        )

    def get_bytes(self, ref: DataRef | Mapping[str, Any] | str) -> bytes:
        key = _ref_uri(ref)
        with self._lock:
            return bytes(self._data[key])


class FilesystemArtifactBackend(ArtifactBackend):
    def __init__(self, *, base_dir: str | Path = "runs/l0_artifacts") -> None:
        self.base_dir = Path(base_dir).expanduser().resolve()
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def put_bytes(
        self,
        name: str,
        data: bytes,
        *,
        kind: str = "artifact",
        media_type: str = "application/octet-stream",
        metadata: Optional[Mapping[str, Any]] = None,
    ) -> DataRef:
        rel = str(name).strip().replace("\\", "/").lstrip("/") or f"artifact_{int(time.time() * 1000)}"
        path = (self.base_dir / rel).resolve()
        if not _is_relative_to(path, self.base_dir):
            raise ValueError("artifact path escapes base_dir")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(bytes(data))
        meta_path = path.with_suffix(path.suffix + ".meta.json")
        meta = {
            "uri": str(path),
            "kind": str(kind),
            "backend": "filesystem",
            "media_type": str(media_type),
            "size_bytes": len(data),
            "metadata": dict(metadata or {}),
            "created_at": time.time(),
        }
        meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
        return DataRef(
            uri=str(path),
            kind=kind,
            backend="filesystem",
            media_type=media_type,
            size_bytes=len(data),
            metadata=dict(metadata or {}),
        )

    def get_bytes(self, ref: DataRef | Mapping[str, Any] | str) -> bytes:
        path = Path(_ref_uri(ref)).expanduser().resolve()
        return path.read_bytes()


class InlineDataTransportBackend(DataTransportBackend):
    def send(self, value: Any, *, kind: str = "payload") -> Any:
        return {"transport": "inline_json", "kind": str(kind), "value": value}

    def receive(self, value: Any) -> Any:
        if isinstance(value, Mapping) and value.get("transport") == "inline_json":
            return value.get("value")
        return value


class ArtifactDataTransportBackend(DataTransportBackend):
    def __init__(self, artifact_backend: ArtifactBackend) -> None:
        self.artifact_backend = artifact_backend

    def send(self, value: Any, *, kind: str = "payload") -> DataRef:
        raw = json.dumps(value, ensure_ascii=False, sort_keys=True).encode("utf-8")
        name = f"{kind}/{int(time.time() * 1000)}.json"
        return self.artifact_backend.put_bytes(name, raw, kind=kind, media_type="application/json")

    def receive(self, value: Any) -> Any:
        if isinstance(value, (DataRef, Mapping)) or isinstance(value, str):
            raw = self.artifact_backend.get_bytes(value)
            return json.loads(raw.decode("utf-8"))
        return value


class RedisTaskQueueBackend(TaskQueueBackend):
    def __init__(
        self,
        *,
        redis_url: str = "redis://localhost:6379/0",
        namespace: str = "nsgablack:l0",
        queue_scope: str = "global",
        client: Any = None,
    ) -> None:
        self.client = _make_redis_client(redis_url=redis_url, client=client)
        self.namespace = _normalize_namespace(namespace)
        self.queue_scope = _normalize_queue_scope(queue_scope)

    def task_queue_key(self, run_id: Optional[str] = None) -> str:
        return _task_queue_key(self.namespace, self.queue_scope, run_id)

    def submit(self, task: TaskEnvelope) -> None:
        self.client.rpush(self.task_queue_key(infer_task_run_id(task)), task_to_json(task))

    def submit_many(self, tasks: Sequence[TaskEnvelope]) -> None:
        if not tasks:
            return
        pipe = self.client.pipeline(transaction=False)
        for task in tuple(tasks):
            pipe.rpush(self.task_queue_key(infer_task_run_id(task)), task_to_json(task))
        pipe.execute()

    def claim(self, run_id: Optional[str] = None, *, timeout_seconds: int = 1) -> Optional[TaskEnvelope]:
        item = self.client.blpop(self.task_queue_key(run_id), timeout=int(timeout_seconds))
        if not item:
            return None
        _key, raw = item
        return task_from_json(raw)


class RedisTaskResultBackend(TaskResultBackend):
    def __init__(
        self,
        *,
        redis_url: str = "redis://localhost:6379/0",
        namespace: str = "nsgablack:l0",
        client: Any = None,
        result_ttl_seconds: Optional[int] = 86_400,
    ) -> None:
        self.client = _make_redis_client(redis_url=redis_url, client=client)
        self.namespace = _normalize_namespace(namespace)
        self.result_ttl_seconds = None if result_ttl_seconds is None else int(result_ttl_seconds)

    def result_key(self, run_id: str, task_id: str) -> str:
        return _result_key(self.namespace, run_id, task_id)

    def complete(self, result: TaskResult) -> None:
        key = self.result_key(infer_result_run_id(result), result.task_id)
        raw = result_to_json(result)
        ttl = self.result_ttl_seconds
        if ttl is None or ttl <= 0:
            self.client.set(key, raw)
        else:
            self.client.setex(key, int(ttl), raw)

    def get_result(self, run_id: str, task_id: str) -> Optional[TaskResult]:
        raw = self.client.get(self.result_key(run_id, task_id))
        return None if raw is None else result_from_json(raw)


class RedisTaskStateBackend(TaskStateBackend):
    def __init__(
        self,
        *,
        redis_url: str = "redis://localhost:6379/0",
        namespace: str = "nsgablack:l0",
        client: Any = None,
    ) -> None:
        self.client = _make_redis_client(redis_url=redis_url, client=client)
        self.namespace = _normalize_namespace(namespace)

    def state_key(self, task_id: str) -> str:
        return f"{self.namespace}:state:{str(task_id)}"

    def set_task_state(
        self,
        task_id: str,
        state: Mapping[str, Any],
        *,
        ttl_seconds: Optional[float] = None,
    ) -> None:
        raw = json.dumps(dict(state), ensure_ascii=False, separators=(",", ":"))
        if ttl_seconds is not None and float(ttl_seconds) > 0:
            self.client.setex(self.state_key(task_id), int(ttl_seconds), raw)
        else:
            self.client.set(self.state_key(task_id), raw)

    def get_task_state(self, task_id: str) -> Optional[Dict[str, Any]]:
        raw = self.client.get(self.state_key(task_id))
        if raw is None:
            return None
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8")
        value = json.loads(str(raw))
        return dict(value) if isinstance(value, Mapping) else {}

    def delete_task_state(self, task_id: str) -> None:
        self.client.delete(self.state_key(task_id))


class RedisWorkerRegistryBackend(WorkerRegistryBackend):
    def __init__(
        self,
        *,
        redis_url: str = "redis://localhost:6379/0",
        namespace: str = "nsgablack:l0",
        client: Any = None,
    ) -> None:
        self.client = _make_redis_client(redis_url=redis_url, client=client)
        self.namespace = _normalize_namespace(namespace)

    def worker_key(self, worker_id: str) -> str:
        return f"{self.namespace}:workers:{str(worker_id)}"

    def heartbeat_key(self, worker_id: str) -> str:
        return f"{self.namespace}:workers:{str(worker_id)}:heartbeat"

    def register(self, worker: WorkerDescriptor | Mapping[str, Any], *, ttl_seconds: Optional[float] = None) -> None:
        item = worker if isinstance(worker, WorkerDescriptor) else WorkerDescriptor.from_dict(worker)
        raw = json.dumps(item.as_dict(), ensure_ascii=False, separators=(",", ":"))
        if ttl_seconds is not None and float(ttl_seconds) > 0:
            self.client.setex(self.worker_key(item.worker_id), int(ttl_seconds), raw)
        else:
            self.client.set(self.worker_key(item.worker_id), raw)

    def heartbeat(
        self,
        worker_id: str,
        payload: Optional[Mapping[str, Any]] = None,
        *,
        ttl_seconds: int = 30,
    ) -> None:
        data = {
            "worker_id": str(worker_id),
            "time": time.time(),
            "payload": dict(payload or {}),
        }
        self.client.setex(
            self.heartbeat_key(worker_id),
            int(ttl_seconds),
            json.dumps(data, ensure_ascii=False, separators=(",", ":")),
        )

    def get_worker(self, worker_id: str) -> Optional[WorkerDescriptor]:
        raw = self.client.get(self.worker_key(worker_id))
        if raw is None:
            return None
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8")
        return WorkerDescriptor.from_dict(json.loads(str(raw)))


@dataclass
class L0RuntimeBackend:
    """Combined runtime backend surface used by distributed evaluators."""

    task_queue: TaskQueueBackend
    result_backend: TaskResultBackend
    worker_registry: Optional[WorkerRegistryBackend] = None
    state_backend: Optional[TaskStateBackend] = None
    artifact_backend: Optional[ArtifactBackend] = None
    data_transport: Optional[DataTransportBackend] = None

    def submit(self, task: TaskEnvelope) -> None:
        if self.state_backend is not None:
            self.state_backend.set_task_state(task.task_id, {"status": "queued", "created_at": task.created_at})
        self.task_queue.submit(task)

    def submit_many(self, tasks: Sequence[TaskEnvelope]) -> None:
        if self.state_backend is not None:
            for task in tuple(tasks):
                self.state_backend.set_task_state(task.task_id, {"status": "queued", "created_at": task.created_at})
        self.task_queue.submit_many(tasks)

    def claim(self, run_id: Optional[str] = None, *, timeout_seconds: int = 1) -> Optional[TaskEnvelope]:
        task = self.task_queue.claim(run_id, timeout_seconds=timeout_seconds)
        if task is not None and self.state_backend is not None:
            self.state_backend.set_task_state(task.task_id, {"status": "claimed", "claimed_at": time.time()})
        return task

    def complete(self, result: TaskResult) -> None:
        if self.state_backend is not None:
            self.state_backend.set_task_state(
                result.task_id,
                {
                    "status": str(result.status),
                    "ok": bool(result.ok),
                    "finished_at": result.finished_at,
                    "worker_id": result.worker_id,
                    "error": result.error,
                },
            )
        self.result_backend.complete(result)

    def get_result(self, run_id: str, task_id: str) -> Optional[TaskResult]:
        return self.result_backend.get_result(run_id, task_id)

    def heartbeat(
        self,
        worker_id: str,
        payload: Optional[Mapping[str, Any]] = None,
        *,
        ttl_seconds: int = 30,
    ) -> None:
        if self.worker_registry is not None:
            self.worker_registry.heartbeat(worker_id, payload, ttl_seconds=ttl_seconds)


class InMemoryL0RuntimeBackend(L0RuntimeBackend):
    def __init__(self, *, namespace: str = "nsgablack:l0", queue_scope: str = "global") -> None:
        artifact_backend = InMemoryArtifactBackend()
        super().__init__(
            task_queue=InMemoryTaskQueueBackend(namespace=namespace, queue_scope=queue_scope),
            result_backend=InMemoryTaskResultBackend(namespace=namespace),
            worker_registry=InMemoryWorkerRegistryBackend(),
            state_backend=InMemoryTaskStateBackend(),
            artifact_backend=artifact_backend,
            data_transport=InlineDataTransportBackend(),
        )


class RedisL0RuntimeBackend(L0RuntimeBackend):
    """Compatibility facade over blackbase's durable Redis TaskTransport.

    New code should use ``task_transport``/``claim_task`` directly. The legacy
    envelope-only ``claim`` and result-only ``complete`` methods retain their
    shapes by keeping the opaque lease claim in the worker process.
    """

    def __init__(
        self,
        *,
        redis_url: str = "redis://localhost:6379/0",
        namespace: str = "nsgablack:l0",
        queue_scope: str = "global",
        client: Any = None,
        result_ttl_seconds: Optional[int] = 86_400,
        artifact_base_dir: str | Path = "runs/l0_artifacts",
    ) -> None:
        redis_client = _make_redis_client(redis_url=redis_url, client=client)
        artifact_backend = FilesystemArtifactBackend(base_dir=artifact_base_dir)
        self.redis_url = str(redis_url)
        self._namespace = _normalize_namespace(namespace)
        self._queue_scope = _normalize_queue_scope(queue_scope)
        self.result_ttl_seconds = result_ttl_seconds
        self.task_transport = RedisTaskTransport(
            redis_url=redis_url,
            namespace=self._namespace,
            client=redis_client,
        )
        # Keep the public composite attributes available during migration. Task
        # and result operations below intentionally go through task_transport.
        self.task_queue = self
        self.result_backend = self
        self.worker_registry = self
        self.state_backend = RedisTaskStateBackend(
            redis_url=redis_url,
            namespace=namespace,
            client=redis_client,
        )
        self.artifact_backend = artifact_backend
        self.data_transport = ArtifactDataTransportBackend(artifact_backend)
        self._claims: Dict[str, ClaimedTask] = {}

    def submit(self, task: TaskEnvelope) -> None:
        self.state_backend.set_task_state(
            task.task_id,
            {"status": "queued", "created_at": task.created_at},
        )
        self.task_transport.submit(task)

    def submit_many(self, tasks: Sequence[TaskEnvelope]) -> None:
        for task in tuple(tasks):
            self.submit(task)

    def claim_task(
        self,
        worker: WorkerDescriptor | Mapping[str, Any],
        *,
        run_id: Optional[str] = None,
        timeout_seconds: int = 1,
        lease_seconds: float = 30.0,
        task_types: Sequence[str] = (),
    ) -> Optional[ClaimedTask]:
        deadline = time.monotonic() + max(0.0, float(timeout_seconds))
        while True:
            claim = self.task_transport.claim(
                worker,
                lease_seconds=lease_seconds,
                task_types=task_types,
                namespaces=((str(run_id),) if run_id and self._queue_scope == "run" else ()),
            )
            if claim is not None:
                self._claims[claim.task.task_id] = claim
                self.state_backend.set_task_state(
                    claim.task.task_id,
                    {
                        "status": "claimed",
                        "claimed_at": time.time(),
                        "worker_id": claim.worker_id,
                        "attempt": claim.attempt,
                        "lease_expires_at": claim.lease_expires_at,
                    },
                )
                return claim
            if time.monotonic() >= deadline:
                return None
            time.sleep(0.05)

    def claim(self, run_id: Optional[str] = None, *, timeout_seconds: int = 1) -> Optional[TaskEnvelope]:
        worker = WorkerDescriptor(
            worker_id=f"nsgablack-compat-{uuid4().hex[:12]}",
            executor_backend="redis",
            resource_backend="local",
            capabilities=("cpu", "numpy", "nested_eval", "project_case"),
            offer=ResourceOffer(threads=1024, gpus=0, backend="local"),
            max_inflight=1,
        )
        claim = self.claim_task(
            worker,
            run_id=run_id,
            timeout_seconds=timeout_seconds,
        )
        return None if claim is None else claim.task

    def complete_claim(self, claim: ClaimedTask, result: TaskResult) -> None:
        self._claims.pop(claim.task.task_id, None)
        if result.ok:
            record = self.task_transport.complete(claim, result)
        else:
            record = self.task_transport.fail(claim, result)
        self._record_result_state(result, transport_status=record.status)

    def complete(self, result: TaskResult) -> None:
        claim = self._claims.pop(result.task_id, None)
        if claim is None:
            raise RuntimeError(
                f"No active Redis task lease for task_id='{result.task_id}'; "
                "claim and complete must run in the same worker process"
            )
        if result.ok:
            record = self.task_transport.complete(claim, result)
        else:
            record = self.task_transport.fail(claim, result)
        self._record_result_state(result, transport_status=record.status)

    def get_result(self, run_id: str, task_id: str) -> Optional[TaskResult]:
        _ = run_id
        record = self.task_transport.get(task_id)
        return None if record is None else record.result

    def heartbeat(
        self,
        worker_id: str,
        payload: Optional[Mapping[str, Any]] = None,
        *,
        ttl_seconds: int = 30,
    ) -> None:
        _ = payload, ttl_seconds
        if not self.task_transport.heartbeat_worker(worker_id, status="online"):
            self.task_transport.register_worker(
                WorkerDescriptor(
                    worker_id=str(worker_id),
                    executor_backend="redis",
                    resource_backend="local",
                    capabilities=("cpu", "numpy", "nested_eval"),
                    offer=ResourceOffer(threads=1024, gpus=0, backend="local"),
                    max_inflight=1,
                )
            )

    def register(
        self,
        worker: WorkerDescriptor | Mapping[str, Any],
        *,
        ttl_seconds: Optional[float] = None,
    ) -> None:
        _ = ttl_seconds
        self.task_transport.register_worker(worker)

    def get_worker(self, worker_id: str) -> Optional[WorkerDescriptor]:
        for worker in self.task_transport.list_workers():
            if worker.worker_id == str(worker_id):
                return worker
        return None

    def _record_result_state(
        self,
        result: TaskResult,
        *,
        transport_status: str,
    ) -> None:
        self.state_backend.set_task_state(
            result.task_id,
            {
                "status": str(transport_status),
                "ok": bool(result.ok) if transport_status != "queued" else False,
                "finished_at": result.finished_at,
                "worker_id": result.worker_id,
                "error": result.error,
            },
        )

    @property
    def namespace(self) -> str:
        return self._namespace

    @property
    def queue_scope(self) -> str:
        return self._queue_scope


def _make_redis_client(*, redis_url: str, client: Any = None) -> Any:
    if client is not None:
        return client
    try:
        import redis  # type: ignore
    except Exception as exc:  # pragma: no cover - optional dependency
        raise RuntimeError("Redis L0 backend requires `redis` package.") from exc
    return redis.from_url(str(redis_url))


def _normalize_namespace(namespace: str) -> str:
    return str(namespace or "nsgablack:l0").strip().rstrip(":")


def _normalize_queue_scope(queue_scope: str) -> str:
    scope = str(queue_scope or "global").strip().lower()
    if scope not in {"global", "run"}:
        raise ValueError("queue_scope must be 'global' or 'run'")
    return scope


def _task_queue_key(namespace: str, queue_scope: str, run_id: Optional[str] = None) -> str:
    if str(queue_scope).lower() == "run":
        if not run_id:
            raise ValueError("run_id is required when queue_scope='run'")
        return f"{namespace}:tasks:{run_id}"
    return f"{namespace}:tasks"


def _result_key(namespace: str, run_id: str, task_id: str) -> str:
    return f"{namespace}:results:{str(run_id)}:{str(task_id)}"


def _ref_uri(ref: DataRef | Mapping[str, Any] | str) -> str:
    if isinstance(ref, DataRef):
        return str(ref.uri)
    if isinstance(ref, Mapping):
        return str(ref.get("uri", ""))
    return str(ref)


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False
