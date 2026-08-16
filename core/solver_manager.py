# -*- coding: utf-8 -*-
"""Multi-solver orchestration with hard resource checks (manager only)."""

from __future__ import annotations

from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field, replace
import inspect
import json
import sqlite3
from threading import RLock
from typing import Any, Callable, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple
from uuid import uuid4

import numpy as np

from .nested_solver import InnerRuntimeEvaluator, InnerSolveRequest


@dataclass(frozen=True)
class ResourceOffer:
    """Offered resources from manager (single backend)."""

    threads: int = 1
    gpus: int = 0
    backend: str = "local"
    device_tokens: tuple[str, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        tokens = _normalize_offer_tokens(self.device_tokens)
        gpus = int(self.gpus)
        if not tokens and gpus > 0:
            tokens = tuple(f"cuda:{idx}" for idx in range(gpus))
        if tokens and gpus <= 0:
            gpus = len(tokens)
        object.__setattr__(self, "threads", max(1, int(self.threads)))
        object.__setattr__(self, "gpus", max(0, int(gpus)))
        object.__setattr__(self, "backend", str(self.backend or "local"))
        object.__setattr__(self, "device_tokens", tokens)
        object.__setattr__(self, "metadata", dict(self.metadata))

    def as_dict(self) -> Dict[str, Any]:
        return {
            "threads": int(self.threads),
            "gpus": int(self.gpus),
            "backend": str(self.backend),
            "device_tokens": [str(token) for token in self.device_tokens],
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class ResourceRequest:
    """Requested resources by a solver."""

    threads: int = 1
    gpus: int = 0
    backend: str = "local"
    label: str = ""
    device_tokens: tuple[str, ...] = ()
    lease: Mapping[str, Any] | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        lease = None if self.lease is None else dict(self.lease)
        tokens = _normalize_request_tokens(self.device_tokens)
        if not tokens and lease is not None:
            tokens = _normalize_request_tokens(lease.get("device_tokens", ()))
        gpus = int(self.gpus)
        if not tokens and gpus > 0:
            tokens = tuple("cuda" for _ in range(gpus))
        if tokens and gpus <= 0:
            gpus = _count_gpu_tokens(tokens)
        object.__setattr__(self, "threads", max(0, int(self.threads)))
        object.__setattr__(self, "gpus", max(0, int(gpus)))
        object.__setattr__(self, "backend", str(self.backend or "local"))
        object.__setattr__(self, "label", str(self.label or ""))
        object.__setattr__(self, "device_tokens", tokens)
        object.__setattr__(self, "lease", lease)
        object.__setattr__(self, "metadata", dict(self.metadata))

    def as_dict(self) -> Dict[str, Any]:
        return {
            "threads": int(self.threads),
            "gpus": int(self.gpus),
            "backend": str(self.backend),
            "label": str(self.label),
            "device_tokens": [str(token) for token in self.device_tokens],
            "lease": None if self.lease is None else dict(self.lease),
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class ResourcePolicy:
    mode: str = "strict"  # auto | strict | warn | queue
    gpu_sharing: str = "exclusive"  # exclusive | shared
    cpu_oversubscribe: bool = False
    max_jobs_per_gpu: int | None = None
    gpu_memory_fraction: float | None = None
    lease_ttl_seconds: float | None = None
    heartbeat_interval_seconds: float | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        mode = str(self.mode or "strict").strip().lower()
        sharing = str(self.gpu_sharing or "exclusive").strip().lower()
        if mode not in {"auto", "strict", "warn", "queue"}:
            raise ValueError("ResourcePolicy.mode must be one of: auto, strict, warn, queue")
        if sharing not in {"exclusive", "shared"}:
            raise ValueError("ResourcePolicy.gpu_sharing must be exclusive or shared")
        max_jobs = None if self.max_jobs_per_gpu is None else int(self.max_jobs_per_gpu)
        if max_jobs is not None and max_jobs < 1:
            raise ValueError("ResourcePolicy.max_jobs_per_gpu must be >= 1 when provided")
        fraction = None if self.gpu_memory_fraction is None else float(self.gpu_memory_fraction)
        if fraction is not None and not (0.0 < fraction <= 1.0):
            raise ValueError("ResourcePolicy.gpu_memory_fraction must be in (0, 1]")
        lease_ttl = _optional_positive_float(self.lease_ttl_seconds, "ResourcePolicy.lease_ttl_seconds")
        heartbeat_interval = _optional_positive_float(
            self.heartbeat_interval_seconds,
            "ResourcePolicy.heartbeat_interval_seconds",
        )
        object.__setattr__(self, "mode", mode)
        object.__setattr__(self, "gpu_sharing", sharing)
        object.__setattr__(self, "max_jobs_per_gpu", max_jobs)
        object.__setattr__(self, "gpu_memory_fraction", fraction)
        object.__setattr__(self, "lease_ttl_seconds", lease_ttl)
        object.__setattr__(self, "heartbeat_interval_seconds", heartbeat_interval)
        object.__setattr__(self, "metadata", dict(self.metadata))

    def as_dict(self) -> Dict[str, Any]:
        return {
            "mode": str(self.mode),
            "gpu_sharing": str(self.gpu_sharing),
            "cpu_oversubscribe": bool(self.cpu_oversubscribe),
            "max_jobs_per_gpu": None if self.max_jobs_per_gpu is None else int(self.max_jobs_per_gpu),
            "gpu_memory_fraction": self.gpu_memory_fraction,
            "lease_ttl_seconds": self.lease_ttl_seconds,
            "heartbeat_interval_seconds": self.heartbeat_interval_seconds,
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class ResourceLease:
    lease_id: str
    owner_id: str
    scope: str
    threads: int
    backend: str = "local"
    device_tokens: tuple[str, ...] = ()
    policy: ResourcePolicy | Mapping[str, Any] = field(default_factory=ResourcePolicy)
    parent_lease_id: str | None = None
    ttl_seconds: float | None = None
    heartbeat_interval_seconds: float | None = None
    acquired_at: float = 0.0
    last_heartbeat_at: float = 0.0
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        policy = _coerce_policy(self.policy)
        ttl_seconds = _optional_positive_float(
            self.ttl_seconds if self.ttl_seconds is not None else policy.lease_ttl_seconds,
            "ResourceLease.ttl_seconds",
        )
        heartbeat_interval = _optional_positive_float(
            self.heartbeat_interval_seconds
            if self.heartbeat_interval_seconds is not None
            else policy.heartbeat_interval_seconds,
            "ResourceLease.heartbeat_interval_seconds",
        )
        acquired_at = float(self.acquired_at or _now_unix())
        last_heartbeat_at = float(self.last_heartbeat_at or acquired_at)
        object.__setattr__(self, "lease_id", str(self.lease_id or uuid4().hex))
        object.__setattr__(self, "owner_id", str(self.owner_id or "outer"))
        object.__setattr__(self, "scope", str(self.scope or "evaluation"))
        object.__setattr__(self, "threads", max(1, int(self.threads)))
        object.__setattr__(self, "backend", str(self.backend or "local"))
        object.__setattr__(self, "device_tokens", _normalize_offer_tokens(self.device_tokens))
        object.__setattr__(self, "policy", policy)
        object.__setattr__(self, "parent_lease_id", None if self.parent_lease_id is None else str(self.parent_lease_id))
        object.__setattr__(self, "ttl_seconds", ttl_seconds)
        object.__setattr__(self, "heartbeat_interval_seconds", heartbeat_interval)
        object.__setattr__(self, "acquired_at", acquired_at)
        object.__setattr__(self, "last_heartbeat_at", last_heartbeat_at)
        object.__setattr__(self, "metadata", dict(self.metadata))

    @property
    def gpus(self) -> int:
        return _count_gpu_tokens(tuple(self.device_tokens))

    @property
    def expires_at(self) -> float | None:
        if self.ttl_seconds is None:
            return None
        return float(self.last_heartbeat_at) + float(self.ttl_seconds)

    def is_expired(self, *, now: float | None = None) -> bool:
        expires_at = self.expires_at
        return expires_at is not None and float(now if now is not None else _now_unix()) >= float(expires_at)

    def with_heartbeat(self, *, at: float | None = None) -> "ResourceLease":
        return replace(self, last_heartbeat_at=float(at if at is not None else _now_unix()))

    def as_dict(self) -> Dict[str, Any]:
        return {
            "lease_id": str(self.lease_id),
            "owner_id": str(self.owner_id),
            "scope": str(self.scope),
            "threads": int(self.threads),
            "backend": str(self.backend),
            "device_tokens": [str(token) for token in self.device_tokens],
            "gpus": int(self.gpus),
            "policy": self.policy.as_dict(),
            "parent_lease_id": self.parent_lease_id,
            "ttl_seconds": self.ttl_seconds,
            "heartbeat_interval_seconds": self.heartbeat_interval_seconds,
            "acquired_at": float(self.acquired_at),
            "last_heartbeat_at": float(self.last_heartbeat_at),
            "expires_at": self.expires_at,
            "metadata": dict(self.metadata),
        }

    def resource_context(
        self,
        *,
        compute_backend: str = "auto",
        device: str = "auto",
        execution_backend: str | None = None,
        namespace: str = "",
        metadata: Mapping[str, Any] | None = None,
    ) -> Dict[str, Any]:
        payload = {
            "scope": str(self.scope),
            "execution_backend": str(execution_backend or self.backend or "serial"),
            "compute_backend": str(compute_backend),
            "device": str(device),
            "threads": int(self.threads),
            "nested": True,
            "namespace": str(namespace or self.owner_id),
            "grant": {
                "phase": str(self.scope),
                "threads": int(self.threads),
                "backend": str(execution_backend or self.backend or "serial"),
                "label": str(self.lease_id),
                "request_label": str(self.owner_id),
                "device_tokens": [str(token) for token in self.device_tokens],
                "metadata": {
                    "resource_lease": self.as_dict(),
                    "parent_scope": "nsgablack_outer",
                },
            },
            "lease": self.as_dict(),
            "metadata": {
                "parent_scope": "nsgablack_outer",
                "resource_lease": self.as_dict(),
            },
        }
        if metadata:
            payload["metadata"].update(dict(metadata))
        if str(device).strip().lower() in {"", "auto", "none"} and self.device_tokens:
            payload["device"] = str(self.device_tokens[0])
        return payload


class ResourceAllocator:
    def __init__(
        self,
        *,
        offer: ResourceOffer,
        policy: ResourcePolicy | Mapping[str, Any] | None = None,
        lease_store: Any | None = None,
        message_queue: Any | None = None,
        queue_strict: bool = False,
    ) -> None:
        self.offer = offer
        self.policy = _coerce_policy(policy)
        if lease_store is None:
            self.lease_store = InMemoryLeaseStore(message_queue=message_queue, queue_strict=queue_strict)
        else:
            self.lease_store = lease_store
            if message_queue is not None:
                set_queue = getattr(self.lease_store, "set_message_queue", None)
                if not callable(set_queue):
                    raise TypeError("lease_store does not support message_queue injection")
                set_queue(message_queue, queue_strict=queue_strict)
        self._lock = RLock()

    def acquire(
        self,
        request: ResourceRequest | Mapping[str, Any],
        *,
        owner_id: str = "",
        scope: str = "outer_evaluation",
        policy: ResourcePolicy | Mapping[str, Any] | None = None,
    ) -> ResourceLease:
        req = _coerce_request(request, label=owner_id or scope)
        effective_policy = _coerce_policy(policy or self.policy)
        try:
            threads = _grant_threads(req, self.offer, effective_policy)
        except ResourceBudgetError as exc:
            _publish_lease_store_event(
                self.lease_store,
                "resource.lease.conflict",
                {
                    "request": req.as_dict(),
                    "errors": [str(exc)],
                    "active_lease_ids": [],
                    "stage": "allocator.thread_grant",
                },
            )
            raise
        with self._lock:
            active = {str(lease.lease_id): lease for lease in tuple(self.lease_store.active_leases())}
            try:
                tokens = _resolve_request_tokens(req, self.offer, active, effective_policy)
            except ResourceBudgetError as exc:
                _publish_lease_store_event(
                    self.lease_store,
                    "resource.lease.conflict",
                    {
                        "request": req.as_dict(),
                        "errors": [str(exc)],
                        "active_lease_ids": sorted(str(lease_id) for lease_id in active),
                        "stage": "allocator.device_resolution",
                    },
                )
                raise
            lease = ResourceLease(
                lease_id=f"{scope}_{uuid4().hex[:12]}",
                owner_id=str(owner_id or req.label or "outer"),
                scope=str(scope),
                threads=int(threads),
                backend=str(req.backend),
                device_tokens=tuple(tokens),
                policy=effective_policy,
                metadata={"request": req.as_dict(), "offer": self.offer.as_dict(), "allocator": "nsgablack.ResourceAllocator"},
            )
            self.lease_store.acquire(lease)
            return lease

    def release(self, lease: ResourceLease | Mapping[str, Any] | str) -> None:
        lease_id = str(lease if isinstance(lease, str) else _coerce_lease(lease).lease_id)
        with self._lock:
            self.lease_store.release(lease_id)

    def heartbeat(self, lease: ResourceLease | Mapping[str, Any] | str) -> bool:
        heartbeat = getattr(self.lease_store, "heartbeat", None)
        if not callable(heartbeat):
            return False
        lease_id = str(lease if isinstance(lease, str) else _coerce_lease(lease).lease_id)
        with self._lock:
            return bool(heartbeat(lease_id))

    def prune_expired(self) -> tuple[ResourceLease, ...]:
        prune = getattr(self.lease_store, "prune_expired", None)
        if not callable(prune):
            return tuple()
        with self._lock:
            return tuple(prune())

    def active_leases(self) -> tuple[ResourceLease, ...]:
        with self._lock:
            return tuple(self.lease_store.active_leases())


@dataclass(frozen=True)
class RegimeSpec:
    name: str
    build_solver: Callable[[], Any]


@dataclass(frozen=True)
class PhaseSpec:
    name: str
    regime_names: tuple[str, ...]


class ResourceBudgetError(RuntimeError):
    pass


@dataclass(frozen=True)
class ResourceEvent:
    """JSON-compatible notification emitted by the L0 resource layer."""

    event_id: str
    topic: str
    payload: Mapping[str, Any] = field(default_factory=dict)
    created_at: float = 0.0
    consumed_at: float | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "event_id", str(self.event_id or uuid4().hex))
        object.__setattr__(self, "topic", str(self.topic or "resource.event"))
        object.__setattr__(self, "payload", dict(self.payload))
        object.__setattr__(self, "created_at", float(self.created_at or _now_unix()))
        consumed = self.consumed_at
        object.__setattr__(self, "consumed_at", None if consumed is None else float(consumed))

    def as_dict(self) -> Dict[str, Any]:
        return {
            "event_id": str(self.event_id),
            "topic": str(self.topic),
            "payload": dict(self.payload),
            "created_at": float(self.created_at),
            "consumed_at": self.consumed_at,
        }


class InMemoryMessageQueue:
    """Process-local resource event queue.

    This is a notification channel, not the resource lock source of truth.
    """

    def __init__(self) -> None:
        self._events: list[ResourceEvent] = []
        self._lock = RLock()

    def publish(self, topic: str, payload: Mapping[str, Any] | None = None) -> ResourceEvent:
        event = ResourceEvent(
            event_id=f"evt_{uuid4().hex[:16]}",
            topic=str(topic),
            payload=dict(payload or {}),
            created_at=_now_unix(),
        )
        with self._lock:
            self._events.append(event)
        return event

    def peek(
        self,
        *,
        topic: str | None = None,
        limit: int = 100,
        include_consumed: bool = False,
    ) -> tuple[ResourceEvent, ...]:
        max_items = max(0, int(limit))
        if max_items <= 0:
            return tuple()
        with self._lock:
            events = tuple(self._events)
        if topic is not None:
            events = tuple(event for event in events if str(event.topic) == str(topic))
        if not include_consumed:
            events = tuple(event for event in events if event.consumed_at is None)
        return tuple(events[:max_items])

    def ack(self, event_id: str) -> bool:
        key = str(event_id)
        with self._lock:
            for idx, event in enumerate(self._events):
                if str(event.event_id) != key:
                    continue
                if event.consumed_at is None:
                    self._events[idx] = replace(event, consumed_at=_now_unix())
                return True
        return False


class SQLiteMessageQueue:
    """SQLite-backed resource event queue for local multi-process notification."""

    def __init__(self, path: str, *, timeout: float = 30.0) -> None:
        self.path = str(path)
        self.timeout = float(timeout)
        self._init_schema()

    def publish(self, topic: str, payload: Mapping[str, Any] | None = None) -> ResourceEvent:
        event = ResourceEvent(
            event_id=f"evt_{uuid4().hex[:16]}",
            topic=str(topic),
            payload=dict(payload or {}),
            created_at=_now_unix(),
        )
        conn = self._connect()
        try:
            conn.execute(
                """
                INSERT INTO resource_events (event_id, topic, payload_json, created_at, consumed_at)
                VALUES (?, ?, ?, ?, NULL)
                """,
                (
                    str(event.event_id),
                    str(event.topic),
                    _json_dumps(dict(event.payload)),
                    float(event.created_at),
                ),
            )
            conn.commit()
        finally:
            conn.close()
        return event

    def peek(
        self,
        *,
        topic: str | None = None,
        limit: int = 100,
        include_consumed: bool = False,
    ) -> tuple[ResourceEvent, ...]:
        max_items = max(0, int(limit))
        if max_items <= 0:
            return tuple()
        clauses: list[str] = []
        params: list[Any] = []
        if topic is not None:
            clauses.append("topic = ?")
            params.append(str(topic))
        if not include_consumed:
            clauses.append("consumed_at IS NULL")
        where = "" if not clauses else "WHERE " + " AND ".join(clauses)
        conn = self._connect()
        try:
            rows = conn.execute(
                f"""
                SELECT event_id, topic, payload_json, created_at, consumed_at
                FROM resource_events
                {where}
                ORDER BY created_at ASC
                LIMIT ?
                """,
                tuple(params + [max_items]),
            ).fetchall()
        finally:
            conn.close()
        return tuple(
            ResourceEvent(
                event_id=str(row["event_id"]),
                topic=str(row["topic"]),
                payload=_json_loads(str(row["payload_json"])),
                created_at=float(row["created_at"]),
                consumed_at=row["consumed_at"],
            )
            for row in rows
        )

    def ack(self, event_id: str) -> bool:
        conn = self._connect()
        try:
            cur = conn.execute(
                "UPDATE resource_events SET consumed_at = ? WHERE event_id = ? AND consumed_at IS NULL",
                (float(_now_unix()), str(event_id)),
            )
            conn.commit()
            return int(cur.rowcount or 0) > 0
        finally:
            conn.close()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path, timeout=float(self.timeout), isolation_level=None)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_schema(self) -> None:
        conn = self._connect()
        try:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS resource_events (
                    event_id TEXT PRIMARY KEY,
                    topic TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    created_at REAL NOT NULL,
                    consumed_at REAL
                )
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_resource_events_topic ON resource_events(topic)")
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_resource_events_consumed ON resource_events(consumed_at)"
            )
            conn.commit()
        finally:
            conn.close()


class InMemoryLeaseStore:
    """Process-local lease store.

    This is enough for serial/thread execution inside one Python process. Use
    SQLiteLeaseStore for process pools or multiple Python processes.
    """

    def __init__(self, *, message_queue: Any | None = None, queue_strict: bool = False) -> None:
        self._active: Dict[str, ResourceLease] = {}
        self._lock = RLock()
        self.message_queue = message_queue
        self.queue_strict = bool(queue_strict)

    def set_message_queue(self, message_queue: Any | None, *, queue_strict: bool | None = None) -> None:
        self.message_queue = message_queue
        if queue_strict is not None:
            self.queue_strict = bool(queue_strict)

    def acquire(self, lease: ResourceLease | Mapping[str, Any]) -> ResourceLease:
        normalized = _coerce_lease(lease)
        with self._lock:
            stale = self._prune_expired_locked(_now_unix())
            errors = _lease_conflict_errors(normalized, tuple(self._active.values()))
            if errors:
                self._publish_expired(stale)
                _publish_resource_event(
                    self.message_queue,
                    self.queue_strict,
                    "resource.lease.conflict",
                    {
                        "lease": normalized.as_dict(),
                        "errors": list(errors),
                        "active_lease_ids": sorted(str(item.lease_id) for item in self._active.values()),
                    },
                )
                raise ResourceBudgetError("; ".join(errors))
            self._active[str(normalized.lease_id)] = normalized
        self._publish_expired(stale)
        _publish_resource_event(
            self.message_queue,
            self.queue_strict,
            "resource.lease.acquired",
            {"lease": normalized.as_dict()},
        )
        return normalized

    def release(self, lease: ResourceLease | Mapping[str, Any] | str) -> None:
        lease_id = str(lease if isinstance(lease, str) else _coerce_lease(lease).lease_id)
        with self._lock:
            released = self._active.pop(lease_id, None)
        _publish_resource_event(
            self.message_queue,
            self.queue_strict,
            "resource.lease.released",
            {"lease_id": lease_id, "lease": None if released is None else released.as_dict()},
        )

    def heartbeat(self, lease: ResourceLease | Mapping[str, Any] | str) -> bool:
        lease_id = str(lease if isinstance(lease, str) else _coerce_lease(lease).lease_id)
        now = _now_unix()
        with self._lock:
            stale = self._prune_expired_locked(now)
            current = self._active.get(lease_id)
            if current is None:
                updated = None
            else:
                updated = current.with_heartbeat(at=now)
                self._active[lease_id] = updated
        self._publish_expired(stale)
        if updated is None:
            return False
        _publish_resource_event(
            self.message_queue,
            self.queue_strict,
            "resource.lease.heartbeat",
            {"lease": updated.as_dict()},
        )
        return True

    def prune_expired(self) -> tuple[ResourceLease, ...]:
        with self._lock:
            stale = self._prune_expired_locked(_now_unix())
        self._publish_expired(stale)
        return stale

    def active_leases(self) -> tuple[ResourceLease, ...]:
        with self._lock:
            stale = self._prune_expired_locked(_now_unix())
            active = tuple(self._active.values())
        self._publish_expired(stale)
        return active

    def _prune_expired_locked(self, now: float) -> tuple[ResourceLease, ...]:
        stale = tuple(lease for lease in self._active.values() if lease.is_expired(now=now))
        for lease in stale:
            self._active.pop(str(lease.lease_id), None)
        return stale

    def _publish_expired(self, stale: Sequence[ResourceLease]) -> None:
        for lease in tuple(stale):
            _publish_resource_event(
                self.message_queue,
                self.queue_strict,
                "resource.lease.expired",
                {"lease": lease.as_dict()},
            )


class SQLiteLeaseStore:
    """SQLite-backed lease store for local multi-process GPU/device leases."""

    def __init__(
        self,
        path: str,
        *,
        timeout: float = 30.0,
        message_queue: Any | None = None,
        queue_strict: bool = False,
    ) -> None:
        self.path = str(path)
        self.timeout = float(timeout)
        self.message_queue = message_queue
        self.queue_strict = bool(queue_strict)
        self._init_schema()

    def set_message_queue(self, message_queue: Any | None, *, queue_strict: bool | None = None) -> None:
        self.message_queue = message_queue
        if queue_strict is not None:
            self.queue_strict = bool(queue_strict)

    def acquire(self, lease: ResourceLease | Mapping[str, Any]) -> ResourceLease:
        normalized = _coerce_lease(lease)
        events: list[tuple[str, Dict[str, Any]]] = []
        committed = False
        conn = self._connect()
        try:
            conn.execute("BEGIN IMMEDIATE")
            stale = self._prune_expired(conn, _now_unix())
            events.extend(("resource.lease.expired", {"lease": item.as_dict()}) for item in stale)
            active = self._active_leases(conn)
            errors = _lease_conflict_errors(normalized, active)
            if errors:
                events.append(
                    (
                        "resource.lease.conflict",
                        {
                            "lease": normalized.as_dict(),
                            "errors": list(errors),
                            "active_lease_ids": sorted(str(item.lease_id) for item in active),
                        },
                    )
                )
                conn.commit()
                committed = True
                raise ResourceBudgetError("; ".join(errors))
            now = _now_unix()
            conn.execute(
                """
                INSERT OR REPLACE INTO resource_leases
                (
                    lease_id,
                    owner_id,
                    scope,
                    threads,
                    backend,
                    policy_json,
                    parent_lease_id,
                    metadata_json,
                    ttl_seconds,
                    heartbeat_interval_seconds,
                    created_at,
                    last_heartbeat_at,
                    released_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL)
                """,
                (
                    str(normalized.lease_id),
                    str(normalized.owner_id),
                    str(normalized.scope),
                    int(normalized.threads),
                    str(normalized.backend),
                    _json_dumps(normalized.policy.as_dict()),
                    normalized.parent_lease_id,
                    _json_dumps(dict(normalized.metadata)),
                    normalized.ttl_seconds,
                    normalized.heartbeat_interval_seconds,
                    float(normalized.acquired_at or now),
                    float(normalized.last_heartbeat_at or now),
                ),
            )
            conn.execute("DELETE FROM resource_lease_devices WHERE lease_id = ?", (str(normalized.lease_id),))
            for token in tuple(normalized.device_tokens):
                conn.execute(
                    "INSERT INTO resource_lease_devices (lease_id, device_token) VALUES (?, ?)",
                    (str(normalized.lease_id), str(token)),
                )
            conn.commit()
            committed = True
            events.append(("resource.lease.acquired", {"lease": normalized.as_dict()}))
            return normalized
        except Exception:
            if not committed:
                conn.rollback()
            raise
        finally:
            conn.close()
            for topic, payload in events:
                _publish_resource_event(self.message_queue, self.queue_strict, topic, payload)

    def release(self, lease: ResourceLease | Mapping[str, Any] | str) -> None:
        lease_id = str(lease if isinstance(lease, str) else _coerce_lease(lease).lease_id)
        event: tuple[str, Dict[str, Any]] | None = None
        conn = self._connect()
        try:
            conn.execute("BEGIN IMMEDIATE")
            active = {str(item.lease_id): item for item in self._active_leases(conn)}
            released = active.get(lease_id)
            conn.execute(
                "UPDATE resource_leases SET released_at = ? WHERE lease_id = ? AND released_at IS NULL",
                (float(_now_unix()), lease_id),
            )
            conn.commit()
            event = (
                "resource.lease.released",
                {"lease_id": lease_id, "lease": None if released is None else released.as_dict()},
            )
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
            if event is not None:
                _publish_resource_event(self.message_queue, self.queue_strict, event[0], event[1])

    def heartbeat(self, lease: ResourceLease | Mapping[str, Any] | str) -> bool:
        lease_id = str(lease if isinstance(lease, str) else _coerce_lease(lease).lease_id)
        events: list[tuple[str, Dict[str, Any]]] = []
        updated: ResourceLease | None = None
        now = _now_unix()
        conn = self._connect()
        try:
            conn.execute("BEGIN IMMEDIATE")
            stale = self._prune_expired(conn, now)
            events.extend(("resource.lease.expired", {"lease": item.as_dict()}) for item in stale)
            active = {str(item.lease_id): item for item in self._active_leases(conn)}
            current = active.get(lease_id)
            if current is not None:
                conn.execute(
                    """
                    UPDATE resource_leases
                    SET last_heartbeat_at = ?
                    WHERE lease_id = ? AND released_at IS NULL
                    """,
                    (float(now), lease_id),
                )
                updated = current.with_heartbeat(at=now)
                events.append(("resource.lease.heartbeat", {"lease": updated.as_dict()}))
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
            for topic, payload in events:
                _publish_resource_event(self.message_queue, self.queue_strict, topic, payload)
        return updated is not None

    def prune_expired(self) -> tuple[ResourceLease, ...]:
        stale: tuple[ResourceLease, ...] = tuple()
        committed = False
        conn = self._connect()
        try:
            conn.execute("BEGIN IMMEDIATE")
            stale = self._prune_expired(conn, _now_unix())
            conn.commit()
            committed = True
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
        to_publish = stale if committed else tuple()
        for lease in to_publish:
            _publish_resource_event(
                self.message_queue,
                self.queue_strict,
                "resource.lease.expired",
                {"lease": lease.as_dict()},
            )
        return stale

    def active_leases(self) -> tuple[ResourceLease, ...]:
        stale: tuple[ResourceLease, ...] = tuple()
        committed = False
        conn = self._connect()
        try:
            conn.execute("BEGIN IMMEDIATE")
            stale = self._prune_expired(conn, _now_unix())
            active = self._active_leases(conn)
            conn.commit()
            committed = True
            return active
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
            to_publish = stale if committed else tuple()
            for lease in to_publish:
                _publish_resource_event(
                    self.message_queue,
                    self.queue_strict,
                    "resource.lease.expired",
                    {"lease": lease.as_dict()},
                )

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path, timeout=float(self.timeout), isolation_level=None)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_schema(self) -> None:
        conn = self._connect()
        try:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS resource_leases (
                    lease_id TEXT PRIMARY KEY,
                    owner_id TEXT NOT NULL,
                    scope TEXT NOT NULL,
                    threads INTEGER NOT NULL,
                    backend TEXT NOT NULL,
                    policy_json TEXT NOT NULL,
                    parent_lease_id TEXT,
                    metadata_json TEXT NOT NULL,
                    ttl_seconds REAL,
                    heartbeat_interval_seconds REAL,
                    created_at REAL NOT NULL,
                    last_heartbeat_at REAL,
                    released_at REAL
                )
                """
            )
            self._ensure_columns(
                conn,
                "resource_leases",
                {
                    "ttl_seconds": "REAL",
                    "heartbeat_interval_seconds": "REAL",
                    "last_heartbeat_at": "REAL",
                },
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS resource_lease_devices (
                    lease_id TEXT NOT NULL,
                    device_token TEXT NOT NULL,
                    PRIMARY KEY (lease_id, device_token),
                    FOREIGN KEY (lease_id) REFERENCES resource_leases(lease_id)
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_resource_lease_devices_token ON resource_lease_devices(device_token)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_resource_leases_released ON resource_leases(released_at)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_resource_leases_heartbeat ON resource_leases(last_heartbeat_at)"
            )
            conn.commit()
        finally:
            conn.close()

    def _ensure_columns(self, conn: sqlite3.Connection, table: str, columns: Mapping[str, str]) -> None:
        existing = {
            str(row["name"])
            for row in conn.execute(f"PRAGMA table_info({table})").fetchall()
        }
        for name, decl in columns.items():
            if str(name) not in existing:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN {name} {decl}")

    def _active_leases(self, conn: sqlite3.Connection) -> tuple[ResourceLease, ...]:
        rows = conn.execute(
            """
            SELECT
                lease_id,
                owner_id,
                scope,
                threads,
                backend,
                policy_json,
                parent_lease_id,
                metadata_json,
                ttl_seconds,
                heartbeat_interval_seconds,
                created_at,
                last_heartbeat_at
            FROM resource_leases
            WHERE released_at IS NULL
            ORDER BY created_at ASC
            """
        ).fetchall()
        out: list[ResourceLease] = []
        for row in rows:
            token_rows = conn.execute(
                "SELECT device_token FROM resource_lease_devices WHERE lease_id = ? ORDER BY device_token ASC",
                (str(row["lease_id"]),),
            ).fetchall()
            out.append(
                ResourceLease(
                    lease_id=str(row["lease_id"]),
                    owner_id=str(row["owner_id"]),
                    scope=str(row["scope"]),
                    threads=int(row["threads"]),
                    backend=str(row["backend"]),
                    device_tokens=tuple(str(item["device_token"]) for item in token_rows),
                    policy=_json_loads(str(row["policy_json"])),
                    parent_lease_id=row["parent_lease_id"],
                    ttl_seconds=row["ttl_seconds"],
                    heartbeat_interval_seconds=row["heartbeat_interval_seconds"],
                    acquired_at=float(row["created_at"]),
                    last_heartbeat_at=float(row["last_heartbeat_at"] or row["created_at"]),
                    metadata=_json_loads(str(row["metadata_json"])),
                )
            )
        return tuple(out)

    def _prune_expired(self, conn: sqlite3.Connection, now: float) -> tuple[ResourceLease, ...]:
        stale = tuple(lease for lease in self._active_leases(conn) if lease.is_expired(now=now))
        for lease in stale:
            conn.execute(
                "UPDATE resource_leases SET released_at = ? WHERE lease_id = ? AND released_at IS NULL",
                (float(now), str(lease.lease_id)),
            )
        return stale


def _coerce_request(value: Any, *, label: str = "") -> ResourceRequest:
    if isinstance(value, ResourceRequest):
        if label and not value.label:
            return ResourceRequest(
                threads=int(value.threads),
                gpus=int(value.gpus),
                backend=str(value.backend),
                label=str(label),
                device_tokens=tuple(value.device_tokens),
                lease=value.lease,
                metadata=dict(value.metadata),
            )
        return value
    if isinstance(value, Mapping):
        lease = value.get("lease", value.get("resource_lease"))
        return ResourceRequest(
            threads=int(value.get("threads", 1) or 1),
            gpus=int(value.get("gpus", 0) or 0),
            backend=str(value.get("backend", "local")),
            label=str(value.get("label", label)),
            device_tokens=tuple(value.get("device_tokens", value.get("devices", value.get("gpu_devices", ())))),
            lease=None if lease is None else dict(lease),
            metadata=dict(value.get("metadata", {}) or {}),
        )
    if isinstance(value, (int, float)):
        return ResourceRequest(threads=int(value), gpus=0, backend="local", label=str(label))
    return ResourceRequest(threads=1, gpus=0, backend="local", label=str(label))


def _infer_request(solver: Any, *, label: str = "") -> ResourceRequest:
    getter = getattr(solver, "resource_request", None)
    if callable(getter):
        try:
            return _coerce_request(getter(), label=label)
        except Exception:
            pass
    value = getattr(solver, "resource_request", None)
    if value is not None and not callable(value):
        try:
            return _coerce_request(value, label=label)
        except Exception:
            pass
    # Conservative default
    return ResourceRequest(threads=1, gpus=0, backend="local", label=str(label))


def _detect_inner_solver(solver: Any) -> Optional[Any]:
    problem = getattr(solver, "problem", None)
    evaluator = getattr(problem, "inner_runtime_evaluator", None) if problem is not None else None
    if isinstance(evaluator, InnerRuntimeEvaluator):
        dim = int(getattr(solver, "dimension", 1) or 1)
        candidate = np.zeros((dim,), dtype=float)
        request = InnerSolveRequest(
            candidate=candidate,
            outer_generation=0,
            outer_individual_id=0,
            budget_units=1.0,
            parent_contract="",
            metadata={},
        )
        try:
            inner_solver = evaluator._build_inner_solver(solver, request)
            if inner_solver is not None:
                return inner_solver
        except Exception:
            return None
    # Fallback: look for explicit hooks on solver/problem
    inner = getattr(solver, "inner_solver", None)
    if inner is not None:
        return inner
    build_inner = getattr(problem, "build_inner_solver", None) if problem is not None else None
    if callable(build_inner):
        try:
            dim = int(getattr(solver, "dimension", 1) or 1)
            candidate = np.zeros((dim,), dtype=float)
            return build_inner(candidate, {"solver": solver, "candidate": candidate})
        except Exception:
            return None
    return None


def _nested_total(request: ResourceRequest, inner: Optional[ResourceRequest]) -> ResourceRequest:
    if inner is None:
        return request
    total_threads = int(request.threads) + int(request.threads) * int(inner.threads)
    total_gpus = int(request.gpus) + int(request.gpus) * int(inner.gpus)
    inner_tokens = tuple(
        token
        for _ in range(max(1, int(request.threads)))
        for token in tuple(inner.device_tokens)
    )
    return ResourceRequest(
        threads=total_threads,
        gpus=total_gpus,
        backend=str(request.backend),
        label=str(request.label),
        device_tokens=tuple(request.device_tokens) + inner_tokens,
        metadata={
            "outer": request.as_dict(),
            "inner": inner.as_dict(),
        },
    )


def _coerce_policy(value: ResourcePolicy | Mapping[str, Any] | None = None) -> ResourcePolicy:
    if isinstance(value, ResourcePolicy):
        return value
    if value is None:
        return ResourcePolicy()
    if not isinstance(value, Mapping):
        raise TypeError("resource policy must be ResourcePolicy, mapping, or None")
    payload = dict(value)
    return ResourcePolicy(
        mode=str(payload.get("mode", "strict")),
        gpu_sharing=str(payload.get("gpu_sharing", payload.get("sharing", "exclusive"))),
        cpu_oversubscribe=bool(payload.get("cpu_oversubscribe", False)),
        max_jobs_per_gpu=payload.get("max_jobs_per_gpu"),
        gpu_memory_fraction=payload.get("gpu_memory_fraction"),
        lease_ttl_seconds=payload.get("lease_ttl_seconds", payload.get("ttl_seconds", payload.get("lease_ttl"))),
        heartbeat_interval_seconds=payload.get(
            "heartbeat_interval_seconds",
            payload.get("heartbeat_interval", payload.get("heartbeat_seconds")),
        ),
        metadata=dict(payload.get("metadata", {}) or {}),
    )


def _coerce_lease(value: ResourceLease | Mapping[str, Any]) -> ResourceLease:
    if isinstance(value, ResourceLease):
        return value
    if not isinstance(value, Mapping):
        raise TypeError("resource lease must be ResourceLease or mapping")
    payload = dict(value)
    return ResourceLease(
        lease_id=str(payload.get("lease_id", "")),
        owner_id=str(payload.get("owner_id", "outer")),
        scope=str(payload.get("scope", "evaluation")),
        threads=int(payload.get("threads", 1)),
        backend=str(payload.get("backend", "local")),
        device_tokens=tuple(payload.get("device_tokens", ())),
        policy=payload.get("policy", {}),
        parent_lease_id=payload.get("parent_lease_id"),
        ttl_seconds=payload.get("ttl_seconds", payload.get("lease_ttl_seconds")),
        heartbeat_interval_seconds=payload.get("heartbeat_interval_seconds"),
        acquired_at=float(payload.get("acquired_at", payload.get("created_at", 0.0)) or 0.0),
        last_heartbeat_at=float(payload.get("last_heartbeat_at", 0.0) or 0.0),
        metadata=dict(payload.get("metadata", {}) or {}),
    )


def _optional_positive_float(value: Any, field_name: str) -> float | None:
    if value is None:
        return None
    out = float(value)
    if out <= 0.0:
        raise ValueError(f"{field_name} must be > 0 when provided")
    return out


def _normalize_device_token(value: Any) -> str:
    key = str(value or "").strip().lower()
    if key in {"", "none", "null", "cpu"}:
        return "cpu"
    if key == "gpu":
        return "cuda"
    if key.isdigit():
        return f"cuda:{int(key)}"
    if key.startswith("gpu:"):
        suffix = key.split(":", 1)[1]
        if suffix.isdigit():
            return f"cuda:{int(suffix)}"
    return key


def _normalize_offer_tokens(values: Sequence[Any]) -> tuple[str, ...]:
    out: list[str] = []
    for raw in tuple(values or ()):
        token = _normalize_device_token(raw)
        if token == "cpu":
            continue
        if token not in out:
            out.append(token)
    return tuple(out)


def _normalize_request_tokens(values: Sequence[Any]) -> tuple[str, ...]:
    out: list[str] = []
    for raw in tuple(values or ()):
        token = _normalize_device_token(raw)
        if token == "cpu":
            continue
        out.append(token)
    return tuple(out)


def _count_gpu_tokens(tokens: Sequence[str]) -> int:
    return sum(1 for token in tuple(tokens) if str(token) == "mps" or str(token).startswith("cuda"))


def _concrete_token(token: str) -> bool:
    return str(token) == "mps" or ":" in str(token)


def _grant_threads(request: ResourceRequest, offer: ResourceOffer, policy: ResourcePolicy) -> int:
    requested = max(1, int(request.threads))
    offered = max(1, int(offer.threads))
    if requested <= offered or bool(policy.cpu_oversubscribe):
        return requested
    if policy.mode in {"auto", "warn"}:
        return offered
    raise ResourceBudgetError(f"threads over budget: request={requested}, offer={offered}")


def _resolve_request_tokens(
    request: ResourceRequest,
    offer: ResourceOffer,
    active: Mapping[str, ResourceLease],
    policy: ResourcePolicy,
) -> tuple[str, ...]:
    requested = tuple(request.device_tokens)
    if not requested:
        return tuple()
    offered = tuple(offer.device_tokens)
    if len(requested) > len(offered) and policy.gpu_sharing == "exclusive":
        raise ResourceBudgetError(f"gpus over budget: request={len(requested)}, offer={len(offered)}")

    resolved: list[str] = []
    for raw in requested:
        token = str(raw)
        if _concrete_token(token):
            selected = token if token in offered else None
        elif token == "cuda":
            selected = _first_available_token(offered, resolved, active, policy, prefix="cuda:")
        elif token == "mps":
            selected = "mps" if "mps" in offered else None
        else:
            selected = None
        if selected is None:
            if policy.mode == "warn":
                selected = token
            else:
                raise ResourceBudgetError(f"requested unavailable device '{token}'")
        if _device_conflicts(selected, active, policy):
            if policy.mode == "warn":
                pass
            else:
                raise ResourceBudgetError(f"device '{selected}' already leased")
        resolved.append(selected)
    return tuple(resolved)


def _first_available_token(
    offered: Sequence[str],
    reserved: Sequence[str],
    active: Mapping[str, ResourceLease],
    policy: ResourcePolicy,
    *,
    prefix: str,
) -> str | None:
    for token in tuple(offered):
        if not str(token).startswith(prefix):
            continue
        if policy.gpu_sharing == "exclusive" and token in set(reserved):
            continue
        if not _device_conflicts(str(token), active, policy):
            return str(token)
    return None


def _device_conflicts(token: str, active: Mapping[str, ResourceLease], policy: ResourcePolicy) -> bool:
    count = 0
    for lease in active.values():
        count += sum(1 for item in tuple(lease.device_tokens) if str(item) == str(token))
    if count <= 0:
        return False
    if policy.gpu_sharing == "exclusive":
        return True
    return count >= int(policy.max_jobs_per_gpu or 1)


def _lease_conflict_errors(lease: ResourceLease, active: Sequence[ResourceLease]) -> list[str]:
    errors: list[str] = []
    new_policy = _coerce_policy(lease.policy)
    for token in tuple(lease.device_tokens):
        active_for_token = [
            item for item in tuple(active)
            if str(token) in {str(active_token) for active_token in tuple(item.device_tokens)}
        ]
        if not active_for_token:
            continue
        if new_policy.gpu_sharing == "exclusive":
            errors.append(f"device '{token}' already leased")
            continue
        for active_lease in active_for_token:
            active_policy = _coerce_policy(active_lease.policy)
            if active_policy.gpu_sharing == "exclusive":
                errors.append(f"device '{token}' already has active exclusive lease '{active_lease.lease_id}'")
                break
            active_limit = int(active_policy.max_jobs_per_gpu or 1)
            if len(active_for_token) + 1 > active_limit:
                errors.append(
                    f"device '{token}' active shared lease limit reached: "
                    f"active={len(active_for_token)}, limit={active_limit}"
                )
                break
        new_limit = int(new_policy.max_jobs_per_gpu or 1)
        if len(active_for_token) + 1 > new_limit:
            errors.append(
                f"device '{token}' requested shared lease limit reached: active={len(active_for_token)}, limit={new_limit}"
            )
    return errors


def _json_dumps(payload: Mapping[str, Any]) -> str:
    return json.dumps(dict(payload), ensure_ascii=False, sort_keys=True)


def _json_loads(text: str) -> Dict[str, Any]:
    try:
        value = json.loads(str(text or "{}"))
    except Exception:
        return {}
    return dict(value) if isinstance(value, Mapping) else {}


def _publish_resource_event(
    message_queue: Any | None,
    queue_strict: bool,
    topic: str,
    payload: Mapping[str, Any],
) -> ResourceEvent | None:
    if message_queue is None:
        return None
    publish = getattr(message_queue, "publish", None)
    if not callable(publish):
        if queue_strict:
            raise TypeError("message_queue must expose publish(topic, payload)")
        return None
    try:
        return publish(str(topic), dict(payload))
    except Exception:
        if queue_strict:
            raise
        return None


def _publish_lease_store_event(lease_store: Any, topic: str, payload: Mapping[str, Any]) -> ResourceEvent | None:
    return _publish_resource_event(
        getattr(lease_store, "message_queue", None),
        bool(getattr(lease_store, "queue_strict", False)),
        topic,
        payload,
    )


def _now_unix() -> float:
    import time

    return float(time.time())


def _merge_results(results: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
    # Minimal merge: keep per-regime results
    return {"regimes": list(results)}


class SolverManager:
    """Legacy in-process multi-solver runner with hard resource checks.

    New cross-Case orchestration belongs to the shared blackbase Project
    substrate. Multi-regime phases here are genuinely concurrent.
    """

    def __init__(
        self,
        *,
        regimes: Sequence[RegimeSpec],
        offer: ResourceOffer,
        phases: Optional[Sequence[PhaseSpec]] = None,
        mode: str = "parallel",
        policy: ResourcePolicy | Mapping[str, Any] | None = None,
    ) -> None:
        self.offer = offer
        self.policy = _coerce_policy(policy)
        self.regimes = {r.name: r for r in regimes}
        if phases is None:
            names = tuple(self.regimes.keys())
            if str(mode).lower() == "serial":
                self.phases = [PhaseSpec(name=f"phase_{i}", regime_names=(n,)) for i, n in enumerate(names)]
            else:
                self.phases = [PhaseSpec(name="phase_parallel", regime_names=names)]
        else:
            self.phases = list(phases)

    def _check_offer(self, req: ResourceRequest) -> None:
        if str(req.backend).strip().lower() != str(self.offer.backend).strip().lower():
            raise ResourceBudgetError(
                f"backend mismatch: request={req.backend}, offer={self.offer.backend}"
            )
        if int(req.threads) > int(self.offer.threads):
            raise ResourceBudgetError(
                f"threads over budget: request={req.threads}, offer={self.offer.threads}"
            )
        if int(req.gpus) > int(self.offer.gpus):
            raise ResourceBudgetError(
                f"gpus over budget: request={req.gpus}, offer={self.offer.gpus}"
            )
        offered = set(str(token) for token in tuple(self.offer.device_tokens))
        for token in tuple(req.device_tokens):
            raw = str(token)
            if raw in {"cuda", "mps"}:
                continue
            if raw not in offered:
                raise ResourceBudgetError(f"requested unavailable device '{raw}'")

    def _check_phase(self, solvers: Sequence[Any]) -> None:
        total_threads = 0
        total_gpus = 0
        concrete_tokens: list[str] = []
        requests: list[ResourceRequest] = []
        for solver in solvers:
            outer = _infer_request(solver, label=getattr(solver, "name", "") or type(solver).__name__)
            inner_solver = _detect_inner_solver(solver)
            inner = _infer_request(inner_solver, label="inner") if inner_solver is not None else None
            total = _nested_total(outer, inner)
            self._check_offer(total)
            requests.append(total)
            total_threads += int(total.threads)
            total_gpus += int(total.gpus)
            concrete_tokens.extend(str(token) for token in tuple(total.device_tokens) if _concrete_token(str(token)))
        if total_threads > int(self.offer.threads):
            raise ResourceBudgetError(
                f"phase threads over budget: need={total_threads}, offer={self.offer.threads}"
            )
        gpu_capacity = int(self.offer.gpus)
        if self.policy.gpu_sharing == "shared":
            gpu_capacity *= int(self.policy.max_jobs_per_gpu or 1)
        if total_gpus > int(gpu_capacity):
            raise ResourceBudgetError(
                f"phase gpus over budget: need={total_gpus}, offer={gpu_capacity}"
            )
        if self.policy.gpu_sharing == "exclusive":
            counts = Counter(concrete_tokens)
            duplicated = sorted(token for token, count in counts.items() if int(count) > 1)
            if duplicated:
                raise ResourceBudgetError(f"phase gpu lease conflict on devices: {duplicated}")
        elif self.policy.max_jobs_per_gpu is not None:
            counts = Counter(concrete_tokens)
            over = sorted(
                token for token, count in counts.items() if int(count) > int(self.policy.max_jobs_per_gpu or 1)
            )
            if over:
                raise ResourceBudgetError(f"phase gpu shared lease limit exceeded on devices: {over}")

    def run(self, *, return_dict: bool = True) -> Dict[str, Any]:
        results: List[Dict[str, Any]] = []
        for phase in self.phases:
            solvers = [self.regimes[name].build_solver() for name in phase.regime_names]
            self._check_phase(solvers)
            if len(solvers) <= 1:
                phase_outputs = [self._run_managed_solver(solvers[0])] if solvers else []
            else:
                with ThreadPoolExecutor(max_workers=len(solvers)) as pool:
                    futures = [pool.submit(self._run_managed_solver, solver) for solver in solvers]
                    phase_outputs = [future.result() for future in futures]
            for solver, out in zip(solvers, phase_outputs):
                results.append(
                    {
                        "regime": getattr(solver, "name", type(solver).__name__),
                        "phase": phase.name,
                        "result": out,
                    }
                )
        merged = _merge_results(results)
        return merged if return_dict else merged

    @staticmethod
    def _run_managed_solver(solver: Any) -> Any:
        run = getattr(solver, "run", None)
        if not callable(run):
            return {}
        try:
            supports_return_dict = "return_dict" in inspect.signature(run).parameters
        except (TypeError, ValueError):
            supports_return_dict = False
        return run(return_dict=True) if supports_return_dict else run()
