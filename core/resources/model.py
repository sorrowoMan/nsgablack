"""Protocol objects for the L0 task/resource orchestration plane."""

from __future__ import annotations

import socket
import time
from dataclasses import dataclass, field
from pathlib import Path
from threading import RLock
from typing import Any, Dict, Mapping, Optional, Sequence
from uuid import uuid4

from ..solver_manager import (
    InMemoryLeaseStore,
    ResourceAllocator,
    ResourceBudgetError,
    ResourceLease,
    ResourceOffer,
    ResourcePolicy,
    ResourceRequest,
)


def _now_unix() -> float:
    return float(time.time())


def _as_tuple(value: Any) -> tuple:
    if value is None:
        return tuple()
    if isinstance(value, str):
        return (value,)
    try:
        return tuple(value)
    except TypeError:
        return (value,)


def _as_float_or_none(value: Any) -> Optional[float]:
    if value is None:
        return None
    out = float(value)
    if out <= 0:
        return None
    return out


@dataclass(frozen=True)
class DataRef:
    """Reference to data or artifact payload that should not be inlined."""

    uri: str
    kind: str = "artifact"
    backend: str = "filesystem"
    media_type: str = ""
    checksum: str = ""
    size_bytes: Optional[int] = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "uri", str(self.uri))
        object.__setattr__(self, "kind", str(self.kind or "artifact"))
        object.__setattr__(self, "backend", str(self.backend or "filesystem"))
        object.__setattr__(self, "media_type", str(self.media_type or ""))
        object.__setattr__(self, "checksum", str(self.checksum or ""))
        size = None if self.size_bytes is None else max(0, int(self.size_bytes))
        object.__setattr__(self, "size_bytes", size)
        object.__setattr__(self, "metadata", dict(self.metadata or {}))

    @classmethod
    def from_path(cls, path: str | Path, *, kind: str = "artifact", media_type: str = "") -> "DataRef":
        p = Path(path)
        size = p.stat().st_size if p.exists() and p.is_file() else None
        return cls(uri=str(p), kind=kind, backend="filesystem", media_type=media_type, size_bytes=size)

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "DataRef":
        return cls(
            uri=str(payload.get("uri", "")),
            kind=str(payload.get("kind", "artifact")),
            backend=str(payload.get("backend", "filesystem")),
            media_type=str(payload.get("media_type", "")),
            checksum=str(payload.get("checksum", "")),
            size_bytes=payload.get("size_bytes"),
            metadata=dict(payload.get("metadata", {}) or {}),
        )

    def as_dict(self) -> Dict[str, Any]:
        return {
            "uri": str(self.uri),
            "kind": str(self.kind),
            "backend": str(self.backend),
            "media_type": str(self.media_type),
            "checksum": str(self.checksum),
            "size_bytes": self.size_bytes,
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class ResourceRequirement:
    """Resource request attached to a task.

    This extends the older ``ResourceRequest`` with memory/capability/timeout
    fields while remaining convertible to the existing lease allocator.
    """

    threads: int = 1
    gpus: int = 0
    resource_backend: str = "local"
    device_tokens: tuple[str, ...] = ()
    memory_mb: Optional[float] = None
    gpu_memory_mb: Optional[float] = None
    capabilities: tuple[str, ...] = ()
    timeout_seconds: Optional[float] = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "threads", max(1, int(self.threads)))
        object.__setattr__(self, "gpus", max(0, int(self.gpus)))
        object.__setattr__(self, "resource_backend", str(self.resource_backend or "local"))
        object.__setattr__(self, "device_tokens", tuple(str(x) for x in _as_tuple(self.device_tokens)))
        object.__setattr__(self, "memory_mb", _as_float_or_none(self.memory_mb))
        object.__setattr__(self, "gpu_memory_mb", _as_float_or_none(self.gpu_memory_mb))
        object.__setattr__(self, "capabilities", tuple(str(x) for x in _as_tuple(self.capabilities) if str(x)))
        object.__setattr__(self, "timeout_seconds", _as_float_or_none(self.timeout_seconds))
        object.__setattr__(self, "metadata", dict(self.metadata or {}))

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "ResourceRequirement":
        return cls(
            threads=int(payload.get("threads", 1) or 1),
            gpus=int(payload.get("gpus", 0) or 0),
            resource_backend=str(payload.get("resource_backend", payload.get("backend", "local"))),
            device_tokens=tuple(payload.get("device_tokens", ()) or ()),
            memory_mb=payload.get("memory_mb"),
            gpu_memory_mb=payload.get("gpu_memory_mb"),
            capabilities=tuple(payload.get("capabilities", ()) or ()),
            timeout_seconds=payload.get("timeout_seconds"),
            metadata=dict(payload.get("metadata", {}) or {}),
        )

    @classmethod
    def from_resource_request(cls, request: ResourceRequest | Mapping[str, Any]) -> "ResourceRequirement":
        req = request if isinstance(request, ResourceRequest) else ResourceRequest(**dict(request))
        metadata = dict(req.metadata or {})
        return cls(
            threads=int(req.threads),
            gpus=int(req.gpus),
            resource_backend=str(req.backend),
            device_tokens=tuple(req.device_tokens),
            memory_mb=metadata.get("memory_mb"),
            gpu_memory_mb=metadata.get("gpu_memory_mb"),
            capabilities=tuple(metadata.get("capabilities", ()) or ()),
            timeout_seconds=metadata.get("timeout_seconds"),
            metadata=metadata,
        )

    def to_resource_request(self, *, label: str = "") -> ResourceRequest:
        metadata = dict(self.metadata)
        if self.memory_mb is not None:
            metadata.setdefault("memory_mb", float(self.memory_mb))
        if self.gpu_memory_mb is not None:
            metadata.setdefault("gpu_memory_mb", float(self.gpu_memory_mb))
        if self.capabilities:
            metadata.setdefault("capabilities", list(self.capabilities))
        if self.timeout_seconds is not None:
            metadata.setdefault("timeout_seconds", float(self.timeout_seconds))
        return ResourceRequest(
            threads=int(self.threads),
            gpus=int(self.gpus),
            backend=str(self.resource_backend),
            label=str(label or ""),
            device_tokens=tuple(self.device_tokens),
            metadata=metadata,
        )

    def as_dict(self) -> Dict[str, Any]:
        return {
            "threads": int(self.threads),
            "gpus": int(self.gpus),
            "resource_backend": str(self.resource_backend),
            "device_tokens": [str(x) for x in self.device_tokens],
            "memory_mb": self.memory_mb,
            "gpu_memory_mb": self.gpu_memory_mb,
            "capabilities": [str(x) for x in self.capabilities],
            "timeout_seconds": self.timeout_seconds,
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class WorkerDescriptor:
    """Execution unit that can receive tasks and owns/declares resources."""

    worker_id: str
    executor_backend: str = "thread"
    resource_backend: str = "local"
    host: str = ""
    capabilities: tuple[str, ...] = ()
    offer: ResourceOffer | Mapping[str, Any] | None = None
    max_inflight: int = 1
    status: str = "online"
    last_heartbeat_at: float = 0.0
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        worker_id = str(self.worker_id or f"worker_{uuid4().hex[:12]}")
        executor_backend = str(self.executor_backend or "thread")
        resource_backend = str(self.resource_backend or "local")
        offer = _coerce_offer(self.offer, resource_backend=resource_backend)
        object.__setattr__(self, "worker_id", worker_id)
        object.__setattr__(self, "executor_backend", executor_backend)
        object.__setattr__(self, "resource_backend", resource_backend)
        object.__setattr__(self, "host", str(self.host or socket.gethostname()))
        object.__setattr__(self, "capabilities", tuple(str(x) for x in _as_tuple(self.capabilities) if str(x)))
        object.__setattr__(self, "offer", offer)
        object.__setattr__(self, "max_inflight", max(1, int(self.max_inflight)))
        object.__setattr__(self, "status", str(self.status or "online"))
        object.__setattr__(self, "last_heartbeat_at", float(self.last_heartbeat_at or _now_unix()))
        object.__setattr__(self, "metadata", dict(self.metadata or {}))

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "WorkerDescriptor":
        return cls(
            worker_id=str(payload.get("worker_id", "")),
            executor_backend=str(payload.get("executor_backend", "thread")),
            resource_backend=str(payload.get("resource_backend", "local")),
            host=str(payload.get("host", "")),
            capabilities=tuple(payload.get("capabilities", ()) or ()),
            offer=dict(payload.get("offer", {}) or {}),
            max_inflight=int(payload.get("max_inflight", 1) or 1),
            status=str(payload.get("status", "online")),
            last_heartbeat_at=float(payload.get("last_heartbeat_at", 0.0) or 0.0),
            metadata=dict(payload.get("metadata", {}) or {}),
        )

    def heartbeat(self, *, status: str = "online", at: Optional[float] = None) -> "WorkerDescriptor":
        return WorkerDescriptor(
            worker_id=self.worker_id,
            executor_backend=self.executor_backend,
            resource_backend=self.resource_backend,
            host=self.host,
            capabilities=self.capabilities,
            offer=self.offer,
            max_inflight=self.max_inflight,
            status=status,
            last_heartbeat_at=float(at if at is not None else _now_unix()),
            metadata=self.metadata,
        )

    def can_run(
        self,
        requirement: ResourceRequirement,
        *,
        executor_backend: str = "auto",
        active_count: int = 0,
    ) -> bool:
        if str(self.status).lower() not in {"online", "idle", "ready"}:
            return False
        if int(active_count) >= int(self.max_inflight):
            return False
        requested_executor = str(executor_backend or "auto").lower()
        if requested_executor not in {"", "auto", "any"} and requested_executor != str(self.executor_backend).lower():
            return False
        if str(requirement.resource_backend).lower() != str(self.resource_backend).lower():
            return False
        caps = set(str(x) for x in self.capabilities)
        if not set(str(x) for x in requirement.capabilities).issubset(caps):
            return False
        offer = self.offer
        if int(requirement.threads) > int(offer.threads):
            return False
        if int(requirement.gpus) > int(offer.gpus):
            return False
        if requirement.device_tokens:
            offered = set(str(x) for x in offer.device_tokens)
            concrete = {x for x in requirement.device_tokens if ":" in str(x) or str(x) == "mps"}
            if not concrete.issubset(offered):
                return False
        if requirement.memory_mb is not None:
            available = dict(offer.metadata or {}).get("memory_mb")
            if available is not None and float(requirement.memory_mb) > float(available):
                return False
        if requirement.gpu_memory_mb is not None:
            if int(requirement.gpus) <= 0 and not requirement.device_tokens:
                return False
            if not _gpu_memory_satisfies_requirement(offer, requirement):
                return False
        return True

    def as_dict(self) -> Dict[str, Any]:
        return {
            "worker_id": str(self.worker_id),
            "executor_backend": str(self.executor_backend),
            "resource_backend": str(self.resource_backend),
            "host": str(self.host),
            "capabilities": [str(x) for x in self.capabilities],
            "offer": self.offer.as_dict(),
            "max_inflight": int(self.max_inflight),
            "status": str(self.status),
            "last_heartbeat_at": float(self.last_heartbeat_at),
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class TaskEnvelope:
    """Serializable L0 task packet."""

    task_id: str
    task_type: str
    payload: Mapping[str, Any] = field(default_factory=dict)
    requirement: ResourceRequirement | Mapping[str, Any] = field(default_factory=ResourceRequirement)
    executor_backend: str = "auto"
    input_refs: tuple[DataRef, ...] = ()
    output_refs: tuple[DataRef, ...] = ()
    parent_task_id: Optional[str] = None
    trace_id: str = ""
    namespace: str = ""
    max_retries: int = 0
    created_at: float = 0.0
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        req = self.requirement if isinstance(self.requirement, ResourceRequirement) else ResourceRequirement.from_dict(self.requirement)
        object.__setattr__(self, "task_id", str(self.task_id or f"task_{uuid4().hex[:16]}"))
        object.__setattr__(self, "task_type", str(self.task_type or "task"))
        object.__setattr__(self, "payload", dict(self.payload or {}))
        object.__setattr__(self, "requirement", req)
        object.__setattr__(self, "executor_backend", str(self.executor_backend or "auto"))
        object.__setattr__(self, "input_refs", tuple(_coerce_data_ref(x) for x in _as_tuple(self.input_refs)))
        object.__setattr__(self, "output_refs", tuple(_coerce_data_ref(x) for x in _as_tuple(self.output_refs)))
        object.__setattr__(self, "parent_task_id", None if self.parent_task_id is None else str(self.parent_task_id))
        object.__setattr__(self, "trace_id", str(self.trace_id or self.task_id))
        object.__setattr__(self, "namespace", str(self.namespace or "default"))
        object.__setattr__(self, "max_retries", max(0, int(self.max_retries)))
        object.__setattr__(self, "created_at", float(self.created_at or _now_unix()))
        object.__setattr__(self, "metadata", dict(self.metadata or {}))

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "TaskEnvelope":
        return cls(
            task_id=str(payload.get("task_id", "")),
            task_type=str(payload.get("task_type", "task")),
            payload=dict(payload.get("payload", {}) or {}),
            requirement=ResourceRequirement.from_dict(dict(payload.get("requirement", {}) or {})),
            executor_backend=str(payload.get("executor_backend", "auto")),
            input_refs=tuple(DataRef.from_dict(x) for x in payload.get("input_refs", ()) or ()),
            output_refs=tuple(DataRef.from_dict(x) for x in payload.get("output_refs", ()) or ()),
            parent_task_id=payload.get("parent_task_id"),
            trace_id=str(payload.get("trace_id", "")),
            namespace=str(payload.get("namespace", "default")),
            max_retries=int(payload.get("max_retries", 0) or 0),
            created_at=float(payload.get("created_at", 0.0) or 0.0),
            metadata=dict(payload.get("metadata", {}) or {}),
        )

    def as_dict(self) -> Dict[str, Any]:
        return {
            "task_id": str(self.task_id),
            "task_type": str(self.task_type),
            "payload": dict(self.payload),
            "requirement": self.requirement.as_dict(),
            "executor_backend": str(self.executor_backend),
            "input_refs": [x.as_dict() for x in self.input_refs],
            "output_refs": [x.as_dict() for x in self.output_refs],
            "parent_task_id": self.parent_task_id,
            "trace_id": str(self.trace_id),
            "namespace": str(self.namespace),
            "max_retries": int(self.max_retries),
            "created_at": float(self.created_at),
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class TaskResult:
    """Serializable task execution result."""

    task_id: str
    status: str
    objectives: tuple[float, ...] = ()
    violations: tuple[float, ...] = ()
    metrics: Mapping[str, Any] = field(default_factory=dict)
    artifact_refs: tuple[DataRef, ...] = ()
    worker_id: str = ""
    lease_id: str = ""
    resource_context: Mapping[str, Any] = field(default_factory=dict)
    error: str = ""
    started_at: float = 0.0
    finished_at: float = 0.0
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        started = float(self.started_at or 0.0)
        finished = float(self.finished_at or (_now_unix() if started else 0.0))
        object.__setattr__(self, "task_id", str(self.task_id))
        object.__setattr__(self, "status", str(self.status or "ok"))
        object.__setattr__(self, "objectives", tuple(float(x) for x in _as_tuple(self.objectives)))
        object.__setattr__(self, "violations", tuple(float(x) for x in _as_tuple(self.violations)))
        object.__setattr__(self, "metrics", dict(self.metrics or {}))
        object.__setattr__(self, "artifact_refs", tuple(_coerce_data_ref(x) for x in _as_tuple(self.artifact_refs)))
        object.__setattr__(self, "worker_id", str(self.worker_id or ""))
        object.__setattr__(self, "lease_id", str(self.lease_id or ""))
        object.__setattr__(self, "resource_context", dict(self.resource_context or {}))
        object.__setattr__(self, "error", str(self.error or ""))
        object.__setattr__(self, "started_at", started)
        object.__setattr__(self, "finished_at", finished)
        object.__setattr__(self, "metadata", dict(self.metadata or {}))

    @property
    def ok(self) -> bool:
        return str(self.status).lower() in {"ok", "success", "completed"}

    @property
    def duration_seconds(self) -> Optional[float]:
        if self.started_at <= 0 or self.finished_at <= 0:
            return None
        return max(0.0, float(self.finished_at) - float(self.started_at))

    @classmethod
    def success(
        cls,
        *,
        task_id: str,
        objectives: Sequence[float] = (),
        violations: Sequence[float] = (),
        worker_id: str = "",
        lease_id: str = "",
        resource_context: Optional[Mapping[str, Any]] = None,
        metrics: Optional[Mapping[str, Any]] = None,
        artifact_refs: Sequence[DataRef | Mapping[str, Any]] = (),
    ) -> "TaskResult":
        return cls(
            task_id=task_id,
            status="ok",
            objectives=tuple(objectives),
            violations=tuple(violations),
            worker_id=worker_id,
            lease_id=lease_id,
            resource_context=dict(resource_context or {}),
            metrics=dict(metrics or {}),
            artifact_refs=tuple(_coerce_data_ref(x) for x in artifact_refs),
            finished_at=_now_unix(),
        )

    @classmethod
    def failure(cls, *, task_id: str, error: str, status: str = "failed", worker_id: str = "") -> "TaskResult":
        return cls(task_id=task_id, status=status, error=error, worker_id=worker_id, finished_at=_now_unix())

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "TaskResult":
        return cls(
            task_id=str(payload.get("task_id", "")),
            status=str(payload.get("status", "ok")),
            objectives=tuple(payload.get("objectives", ()) or ()),
            violations=tuple(payload.get("violations", ()) or ()),
            metrics=dict(payload.get("metrics", {}) or {}),
            artifact_refs=tuple(DataRef.from_dict(x) for x in payload.get("artifact_refs", ()) or ()),
            worker_id=str(payload.get("worker_id", "")),
            lease_id=str(payload.get("lease_id", "")),
            resource_context=dict(payload.get("resource_context", {}) or {}),
            error=str(payload.get("error", "")),
            started_at=float(payload.get("started_at", 0.0) or 0.0),
            finished_at=float(payload.get("finished_at", 0.0) or 0.0),
            metadata=dict(payload.get("metadata", {}) or {}),
        )

    def as_dict(self) -> Dict[str, Any]:
        return {
            "task_id": str(self.task_id),
            "status": str(self.status),
            "ok": bool(self.ok),
            "objectives": [float(x) for x in self.objectives],
            "violations": [float(x) for x in self.violations],
            "metrics": dict(self.metrics),
            "artifact_refs": [x.as_dict() for x in self.artifact_refs],
            "worker_id": str(self.worker_id),
            "lease_id": str(self.lease_id),
            "resource_context": dict(self.resource_context),
            "error": str(self.error),
            "started_at": float(self.started_at),
            "finished_at": float(self.finished_at),
            "duration_seconds": self.duration_seconds,
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class ScheduledTask:
    task: TaskEnvelope
    worker: WorkerDescriptor
    lease: ResourceLease
    resource_context: Mapping[str, Any]

    def as_dict(self) -> Dict[str, Any]:
        return {
            "task": self.task.as_dict(),
            "worker": self.worker.as_dict(),
            "lease": self.lease.as_dict(),
            "resource_context": dict(self.resource_context),
        }


class InMemoryWorkerRegistry:
    """Process-local registry of available L0 workers."""

    def __init__(self, workers: Sequence[WorkerDescriptor | Mapping[str, Any]] = ()) -> None:
        self._workers: Dict[str, WorkerDescriptor] = {}
        self._lock = RLock()
        for worker in workers:
            self.register(worker)

    def register(self, worker: WorkerDescriptor | Mapping[str, Any]) -> WorkerDescriptor:
        item = worker if isinstance(worker, WorkerDescriptor) else WorkerDescriptor.from_dict(worker)
        with self._lock:
            self._workers[str(item.worker_id)] = item
        return item

    def unregister(self, worker_id: str) -> None:
        with self._lock:
            self._workers.pop(str(worker_id), None)

    def heartbeat(self, worker_id: str, *, status: str = "online") -> bool:
        with self._lock:
            current = self._workers.get(str(worker_id))
            if current is None:
                return False
            self._workers[str(worker_id)] = current.heartbeat(status=status)
            return True

    def get(self, worker_id: str) -> Optional[WorkerDescriptor]:
        with self._lock:
            return self._workers.get(str(worker_id))

    def list_workers(self, *, status: Optional[str] = None) -> tuple[WorkerDescriptor, ...]:
        with self._lock:
            values = tuple(self._workers.values())
        if status is None:
            return values
        return tuple(worker for worker in values if str(worker.status).lower() == str(status).lower())


class InMemoryResourceScheduler:
    """Minimal L0 scheduler for local tests and single-process execution.

    The scheduler performs worker capability matching, creates a ResourceLease
    through the existing ResourceAllocator, and tracks lease -> worker mapping.
    It is deliberately small; Redis/Ray/K8s schedulers should implement the
    same task/worker/result contracts instead of copying this policy.
    """

    def __init__(
        self,
        *,
        workers: Sequence[WorkerDescriptor | Mapping[str, Any]] = (),
        policy: ResourcePolicy | Mapping[str, Any] | None = None,
        message_queue: Any = None,
        queue_strict: bool = False,
    ) -> None:
        self.registry = InMemoryWorkerRegistry()
        self.policy = policy if isinstance(policy, ResourcePolicy) else ResourcePolicy(**dict(policy or {}))
        self.message_queue = message_queue
        self.queue_strict = bool(queue_strict)
        self._allocators: Dict[str, ResourceAllocator] = {}
        self._lease_to_worker: Dict[str, str] = {}
        self._inflight: Dict[str, int] = {}
        self._lock = RLock()
        for worker in workers:
            self.register_worker(worker)

    def register_worker(self, worker: WorkerDescriptor | Mapping[str, Any]) -> WorkerDescriptor:
        item = self.registry.register(worker)
        with self._lock:
            self._allocators[str(item.worker_id)] = ResourceAllocator(
                offer=item.offer,
                policy=self.policy,
                lease_store=InMemoryLeaseStore(message_queue=self.message_queue, queue_strict=self.queue_strict),
                message_queue=None,
            )
            self._inflight.setdefault(str(item.worker_id), 0)
        return item

    def acquire(
        self,
        task: TaskEnvelope | Mapping[str, Any],
        *,
        owner_id: str = "",
        scope: str = "task_evaluation",
    ) -> ScheduledTask:
        envelope = task if isinstance(task, TaskEnvelope) else TaskEnvelope.from_dict(task)
        with self._lock:
            worker = self._select_worker_locked(envelope)
            allocator = self._allocators[str(worker.worker_id)]
            request = envelope.requirement.to_resource_request(label=envelope.task_id)
            lease = allocator.acquire(
                request,
                owner_id=str(owner_id or envelope.task_id),
                scope=str(scope or envelope.task_type),
            )
            self._lease_to_worker[str(lease.lease_id)] = str(worker.worker_id)
            self._inflight[str(worker.worker_id)] = int(self._inflight.get(str(worker.worker_id), 0)) + 1
        resource_context = lease.resource_context(
            execution_backend=str(worker.executor_backend),
            namespace=str(envelope.namespace),
            metadata={
                "task_id": str(envelope.task_id),
                "task_type": str(envelope.task_type),
                "worker_id": str(worker.worker_id),
            },
        )
        return ScheduledTask(task=envelope, worker=worker, lease=lease, resource_context=resource_context)

    def release(self, scheduled_or_lease: ScheduledTask | ResourceLease | Mapping[str, Any] | str) -> None:
        lease_id = _extract_lease_id(scheduled_or_lease)
        with self._lock:
            worker_id = self._lease_to_worker.pop(str(lease_id), None)
            if worker_id is None:
                return
            allocator = self._allocators.get(worker_id)
            if allocator is not None:
                allocator.release(str(lease_id))
            self._inflight[worker_id] = max(0, int(self._inflight.get(worker_id, 0)) - 1)

    def heartbeat(self, lease: ScheduledTask | ResourceLease | Mapping[str, Any] | str) -> bool:
        lease_id = _extract_lease_id(lease)
        with self._lock:
            worker_id = self._lease_to_worker.get(str(lease_id))
            if worker_id is None:
                return False
            allocator = self._allocators.get(worker_id)
            return bool(allocator.heartbeat(str(lease_id))) if allocator is not None else False

    def active_leases(self) -> tuple[ResourceLease, ...]:
        with self._lock:
            leases = []
            for allocator in self._allocators.values():
                leases.extend(allocator.active_leases())
        return tuple(leases)

    def _select_worker_locked(self, task: TaskEnvelope) -> WorkerDescriptor:
        workers = self.registry.list_workers()
        for worker in workers:
            active = int(self._inflight.get(str(worker.worker_id), 0))
            if worker.can_run(task.requirement, executor_backend=task.executor_backend, active_count=active):
                return worker
        raise ResourceBudgetError(
            "no worker satisfies task requirement: "
            f"task_id={task.task_id} requirement={task.requirement.as_dict()}"
        )


def _coerce_offer(value: ResourceOffer | Mapping[str, Any] | None, *, resource_backend: str) -> ResourceOffer:
    if isinstance(value, ResourceOffer):
        return value
    payload = dict(value or {})
    metadata = dict(payload.get("metadata", {}) or {})
    if "memory_mb" in payload:
        metadata.setdefault("memory_mb", payload.get("memory_mb"))
    if "gpu_memory_mb" in payload:
        metadata.setdefault("gpu_memory_mb", payload.get("gpu_memory_mb"))
    if "gpu_memory_mb_by_device" in payload:
        metadata.setdefault("gpu_memory_mb_by_device", dict(payload.get("gpu_memory_mb_by_device") or {}))
    return ResourceOffer(
        threads=int(payload.get("threads", 1) or 1),
        gpus=int(payload.get("gpus", 0) or 0),
        backend=str(payload.get("backend", resource_backend)),
        device_tokens=tuple(payload.get("device_tokens", ()) or ()),
        metadata=metadata,
    )


def _gpu_memory_satisfies_requirement(offer: ResourceOffer, requirement: ResourceRequirement) -> bool:
    metadata = dict(offer.metadata or {})
    required = float(requirement.gpu_memory_mb or 0.0)
    if required <= 0:
        return True
    by_device = dict(metadata.get("gpu_memory_mb_by_device", {}) or {})
    requested_tokens = tuple(str(x) for x in requirement.device_tokens)
    concrete_tokens = tuple(x for x in requested_tokens if ":" in x or x == "mps")
    if concrete_tokens and by_device:
        return all(float(by_device.get(token, 0.0) or 0.0) >= required for token in concrete_tokens)
    available_total = metadata.get("gpu_memory_mb")
    if available_total is not None:
        return float(available_total) >= required
    if by_device:
        return any(float(v or 0.0) >= required for v in by_device.values())
    return False


def _coerce_data_ref(value: DataRef | Mapping[str, Any]) -> DataRef:
    if isinstance(value, DataRef):
        return value
    if isinstance(value, Mapping):
        return DataRef.from_dict(value)
    return DataRef(uri=str(value))


def _extract_lease_id(value: ScheduledTask | ResourceLease | Mapping[str, Any] | str) -> str:
    if isinstance(value, ScheduledTask):
        return str(value.lease.lease_id)
    if isinstance(value, ResourceLease):
        return str(value.lease_id)
    if isinstance(value, Mapping):
        return str(value.get("lease_id", value.get("lease", {}).get("lease_id", "")))
    return str(value)
