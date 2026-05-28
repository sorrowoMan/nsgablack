"""L0 resource lease primitives — ResourceOffer, Request, Policy, Lease, Allocator, stores.

Canonical location.  ``core.solver_manager`` re-exports these for backward compat.
"""

from __future__ import annotations

import json
import sqlite3
import time
from collections import Counter
from dataclasses import dataclass, field, replace
from threading import RLock
from typing import Any, Dict, Mapping, Optional, Sequence, Tuple
from uuid import uuid4

import numpy as np


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _now_unix() -> float:
    return time.time()


def _optional_positive_float(value: Optional[float], label: str) -> Optional[float]:
    if value is None:
        return None
    v = float(value)
    if v <= 0.0:
        raise ValueError(f"{label} must be > 0, got {v}")
    return v


def _coerce_policy(policy: Any) -> "ResourcePolicy":
    if isinstance(policy, ResourcePolicy):
        return policy
    if isinstance(policy, Mapping):
        return ResourcePolicy(**dict(policy))
    return ResourcePolicy()


def _normalize_offer_tokens(tokens: Any) -> tuple[str, ...]:
    if tokens is None:
        return ()
    if isinstance(tokens, str):
        return (str(tokens),)
    return tuple(str(t) for t in tokens)


def _normalize_request_tokens(tokens: Any) -> tuple[str, ...]:
    if tokens is None:
        return ()
    if isinstance(tokens, str):
        return (str(tokens),)
    return tuple(str(t) for t in tokens)


def _count_gpu_tokens(tokens: tuple[str, ...]) -> int:
    return max(0, len([t for t in tokens if _is_gpu_token(t)]))


def _is_gpu_token(token: str) -> bool:
    t = str(token).strip().lower()
    return t.startswith("cuda") or t.startswith("gpu") or "cuda" in t


def _coerce_request(
    request: Any, *, label: str = ""
) -> "ResourceRequest":
    if isinstance(request, ResourceRequest):
        return request
    if isinstance(request, Mapping):
        return ResourceRequest(label=str(label), **dict(request))
    raise TypeError(f"ResourceRequest expected, got {type(request).__name__}")


def _grant_threads(
    req: "ResourceRequest", offer: "ResourceOffer", policy: "ResourcePolicy"
) -> int:
    requested = int(req.threads or 1)
    available = int(offer.threads or 1)
    if policy.mode == "strict" and requested > available:
        raise ResourceBudgetError(
            f"threads: requested {requested} > available {available}"
        )
    if policy.mode == "queue":
        return requested
    granted = min(requested, available)
    if not policy.cpu_oversubscribe and granted < requested:
        if policy.mode in {"strict", "auto"}:
            raise ResourceBudgetError(
                f"threads: requested {requested}, can only grant {granted} (oversubscribe disabled)"
            )
    return granted


def _resolve_request_tokens(
    req: "ResourceRequest",
    offer: "ResourceOffer",
    active: Dict[str, "ResourceLease"],
    policy: "ResourcePolicy",
) -> Tuple[str, ...]:
    requested = tuple(req.device_tokens)
    if not requested:
        return ()
    if policy.gpu_sharing == "shared":
        return requested
    max_jobs = policy.max_jobs_per_gpu
    for token in requested:
        count = sum(
            1 for _lease in active.values() if token in _lease.device_tokens
        )
        if max_jobs is not None and count >= int(max_jobs):
            raise ResourceBudgetError(
                f"device token '{token}' exhausted: {count} active >= max {max_jobs}"
            )
    return requested


def _publish_lease_store_event(
    store: Any, topic: str, payload: Dict[str, Any]
) -> None:
    publish = getattr(store, "publish", None)
    if not callable(publish):
        return
    try:
        publish(topic, payload)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# data types
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ResourceOffer:
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
            "device_tokens": [str(t) for t in self.device_tokens],
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class ResourceRequest:
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
            "device_tokens": [str(t) for t in self.device_tokens],
            "lease": None if self.lease is None else dict(self.lease),
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class ResourcePolicy:
    mode: str = "strict"
    gpu_sharing: str = "exclusive"
    cpu_oversubscribe: bool = False
    max_jobs_per_gpu: int | None = None
    gpu_memory_fraction: float | None = None
    lease_ttl_seconds: float | None = None
    heartbeat_interval_seconds: float | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        mode = str(self.mode or "strict").strip().lower()
        if mode not in {"auto", "strict", "warn", "queue"}:
            raise ValueError("mode must be one of: auto, strict, warn, queue")
        sharing = str(self.gpu_sharing or "exclusive").strip().lower()
        if sharing not in {"exclusive", "shared"}:
            raise ValueError("gpu_sharing must be exclusive or shared")
        max_jobs = None if self.max_jobs_per_gpu is None else int(self.max_jobs_per_gpu)
        if max_jobs is not None and max_jobs < 1:
            raise ValueError("max_jobs_per_gpu must be >= 1")
        fraction = None if self.gpu_memory_fraction is None else float(self.gpu_memory_fraction)
        if fraction is not None and not (0.0 < fraction <= 1.0):
            raise ValueError("gpu_memory_fraction must be in (0, 1]")
        object.__setattr__(self, "mode", mode)
        object.__setattr__(self, "gpu_sharing", sharing)
        object.__setattr__(self, "max_jobs_per_gpu", max_jobs)
        object.__setattr__(self, "gpu_memory_fraction", fraction)
        object.__setattr__(self, "lease_ttl_seconds", _optional_positive_float(self.lease_ttl_seconds, "lease_ttl_seconds"))
        object.__setattr__(self, "heartbeat_interval_seconds", _optional_positive_float(self.heartbeat_interval_seconds, "heartbeat_interval_seconds"))
        object.__setattr__(self, "metadata", dict(self.metadata))

    def as_dict(self) -> Dict[str, Any]:
        return {
            "mode": str(self.mode),
            "gpu_sharing": str(self.gpu_sharing),
            "cpu_oversubscribe": bool(self.cpu_oversubscribe),
            "max_jobs_per_gpu": self.max_jobs_per_gpu,
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
            "ttl_seconds",
        )
        heartbeat_interval = _optional_positive_float(
            self.heartbeat_interval_seconds if self.heartbeat_interval_seconds is not None
            else policy.heartbeat_interval_seconds,
            "heartbeat_interval_seconds",
        )
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
        object.__setattr__(self, "acquired_at", float(self.acquired_at or _now_unix()))
        object.__setattr__(self, "last_heartbeat_at", float(self.last_heartbeat_at or self.acquired_at))
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
        expires_at_val = self.expires_at
        return expires_at_val is not None and float(now if now is not None else _now_unix()) >= float(expires_at_val)

    def with_heartbeat(self, *, at: float | None = None) -> "ResourceLease":
        return replace(self, last_heartbeat_at=float(at if at is not None else _now_unix()))

    def as_dict(self) -> Dict[str, Any]:
        return {
            "lease_id": str(self.lease_id),
            "owner_id": str(self.owner_id),
            "scope": str(self.scope),
            "threads": int(self.threads),
            "backend": str(self.backend),
            "device_tokens": [str(t) for t in self.device_tokens],
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

    def resource_context(self, *, compute_backend: str = "auto", device: str = "auto",
                         execution_backend: str | None = None, namespace: str = "",
                         metadata: Mapping[str, Any] | None = None) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
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
                "device_tokens": [str(t) for t in self.device_tokens],
                "metadata": {"resource_lease": self.as_dict(), "parent_scope": "nsgablack_outer"},
            },
            "lease": self.as_dict(),
            "metadata": {"parent_scope": "nsgablack_outer", "resource_lease": self.as_dict()},
        }
        if metadata:
            payload["metadata"].update(dict(metadata))
        if str(device).strip().lower() in {"", "auto", "none"} and self.device_tokens:
            payload["device"] = str(self.device_tokens[0])
        return payload


class ResourceBudgetError(RuntimeError):
    pass


class ResourceAllocator:
    def __init__(self, *, offer: ResourceOffer, policy: ResourcePolicy | Mapping[str, Any] | None = None,
                 lease_store: Any | None = None, message_queue: Any | None = None, queue_strict: bool = False) -> None:
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

    def acquire(self, request: ResourceRequest | Mapping[str, Any], *, owner_id: str = "",
                scope: str = "outer_evaluation",
                policy: ResourcePolicy | Mapping[str, Any] | None = None) -> ResourceLease:
        req = _coerce_request(request, label=owner_id or scope)
        effective_policy = _coerce_policy(policy or self.policy)
        try:
            threads = _grant_threads(req, self.offer, effective_policy)
        except ResourceBudgetError as exc:
            _publish_lease_store_event(self.lease_store, "resource.lease.conflict", {
                "request": req.as_dict(), "errors": [str(exc)], "active_lease_ids": [],
                "stage": "allocator.thread_grant",
            })
            raise
        with self._lock:
            active = {str(l.lease_id): l for l in tuple(self.lease_store.active_leases())}
            try:
                tokens = _resolve_request_tokens(req, self.offer, active, effective_policy)
            except ResourceBudgetError as exc:
                _publish_lease_store_event(self.lease_store, "resource.lease.conflict", {
                    "request": req.as_dict(), "errors": [str(exc)],
                    "active_lease_ids": sorted(str(k) for k in active),
                    "stage": "allocator.device_resolution",
                })
                raise
            lease = ResourceLease(
                lease_id=f"{scope}_{uuid4().hex[:12]}",
                owner_id=str(owner_id or req.label or "outer"),
                scope=str(scope), threads=int(threads),
                backend=str(req.backend), device_tokens=tuple(tokens),
                policy=effective_policy,
                metadata={"request": req.as_dict(), "offer": self.offer.as_dict(), "allocator": "nsgablack.ResourceAllocator"},
            )
            self.lease_store.acquire(lease)
            return lease

    def release(self, lease: ResourceLease | Mapping[str, Any] | str) -> None:
        self.lease_store.release(lease)


class ResourceEvent(dict):
    def __init__(self, event_id: str = "", topic: str = "", payload: Any = None,
                 created_at: float = 0.0, consumed_at: float = 0.0) -> None:
        super().__init__(
            event_id=str(event_id or uuid4().hex),
            topic=str(topic),
            payload=payload,
            created_at=float(created_at or _now_unix()),
            consumed_at=float(consumed_at),
        )


class InMemoryMessageQueue:
    def __init__(self) -> None:
        self._topics: Dict[str, list] = {}
        self._lock = RLock()

    def publish(self, topic: str, payload: Any) -> str:
        eid = uuid4().hex
        event = ResourceEvent(event_id=eid, topic=topic, payload=payload)
        with self._lock:
            self._topics.setdefault(str(topic), []).append(event)
        return eid

    def peek(self, topic: str, limit: int = 10) -> list:
        with self._lock:
            return [dict(e) for e in self._topics.get(str(topic), [])[:int(limit)]]

    def ack(self, event_id: str) -> bool:
        with self._lock:
            for lst in self._topics.values():
                for i, e in enumerate(lst):
                    if e.get("event_id") == str(event_id):
                        lst.pop(i)
                        return True
        return False


class SQLiteMessageQueue:
    def __init__(self, path: str = ":memory:") -> None:
        self._conn = sqlite3.connect(str(path), check_same_thread=False)
        self._conn.execute("CREATE TABLE IF NOT EXISTS messages (event_id TEXT PRIMARY KEY, topic TEXT, payload_json TEXT, created_at REAL, consumed_at REAL)")
        self._conn.commit()

    def publish(self, topic: str, payload: Any) -> str:
        eid = uuid4().hex
        self._conn.execute(
            "INSERT OR REPLACE INTO messages VALUES (?,?,?,?,?)",
            (eid, str(topic), json.dumps(payload), _now_unix(), 0.0),
        )
        self._conn.commit()
        return eid

    def peek(self, topic: str, limit: int = 10) -> list:
        rows = self._conn.execute(
            "SELECT event_id, topic, payload_json, created_at FROM messages WHERE topic=? LIMIT ?",
            (str(topic), int(limit)),
        ).fetchall()
        return [
            {"event_id": r[0], "topic": r[1], "payload": json.loads(r[2]), "created_at": r[3]}
            for r in rows
        ]

    def ack(self, event_id: str) -> bool:
        cur = self._conn.execute("DELETE FROM messages WHERE event_id=?", (str(event_id),))
        self._conn.commit()
        return cur.rowcount > 0


class InMemoryLeaseStore:
    def __init__(self, *, message_queue: Any | None = None, queue_strict: bool = False) -> None:
        self._leases: Dict[str, ResourceLease] = {}
        self._lock = RLock()
        self._message_queue = message_queue
        self._queue_strict = bool(queue_strict)

    def set_message_queue(self, mq: Any, *, queue_strict: bool = False) -> None:
        self._message_queue = mq
        self._queue_strict = bool(queue_strict)

    def publish(self, topic: str, payload: Any) -> None:
        mq = self._message_queue
        if mq is None:
            return
        pub = getattr(mq, "publish", None)
        if not callable(pub):
            return
        pub(topic, payload)

    def acquire(self, lease: ResourceLease) -> None:
        with self._lock:
            lid = str(lease.lease_id)
            self._leases[lid] = lease

    def release(self, lease: ResourceLease | str) -> None:
        lid = lease if isinstance(lease, str) else str(getattr(lease, "lease_id", ""))
        with self._lock:
            self._leases.pop(lid, None)

    def active_leases(self) -> tuple[ResourceLease, ...]:
        with self._lock:
            return tuple(self._leases.values())

    def heartbeat(self, lease_id: str) -> ResourceLease | None:
        with self._lock:
            l = self._leases.get(str(lease_id))
            if l is not None:
                l = l.with_heartbeat()
                self._leases[str(lease_id)] = l
            return l

    def prune_expired(self) -> int:
        removed = 0
        with self._lock:
            expired = [lid for lid, l in self._leases.items() if l.is_expired()]
            for lid in expired:
                self._leases.pop(lid, None)
                removed += 1
        return removed


class SQLiteLeaseStore:
    def __init__(self, path: str = ":memory:", *, message_queue: Any | None = None) -> None:
        self._conn = sqlite3.connect(str(path), check_same_thread=False)
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS leases (lease_id TEXT PRIMARY KEY, owner_id TEXT, scope TEXT, "
            "threads INTEGER, backend TEXT, device_tokens_json TEXT, policy_json TEXT, "
            "parent_lease_id TEXT, ttl_seconds REAL, heartbeat_interval_seconds REAL, "
            "acquired_at REAL, last_heartbeat_at REAL, metadata_json TEXT)"
        )
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS lease_devices (lease_id TEXT, token TEXT, PRIMARY KEY(lease_id, token))"
        )
        self._conn.commit()
        self._message_queue = message_queue
        self._lock = RLock()

    def set_message_queue(self, mq: Any, *, queue_strict: bool = False) -> None:
        self._message_queue = mq

    def publish(self, topic: str, payload: Any) -> None:
        mq = self._message_queue
        if mq is None:
            return
        pub = getattr(mq, "publish", None)
        if callable(pub):
            pub(topic, payload)

    def acquire(self, lease: ResourceLease) -> None:
        with self._lock:
            self._conn.execute("BEGIN IMMEDIATE")
            try:
                self._conn.execute(
                    "INSERT OR REPLACE INTO leases VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (str(lease.lease_id), str(lease.owner_id), str(lease.scope), int(lease.threads),
                     str(lease.backend), json.dumps(list(lease.device_tokens)),
                     json.dumps(lease.policy.as_dict()), lease.parent_lease_id,
                     lease.ttl_seconds, lease.heartbeat_interval_seconds,
                     float(lease.acquired_at), float(lease.last_heartbeat_at),
                     json.dumps(dict(lease.metadata))),
                )
                for t in lease.device_tokens:
                    self._conn.execute(
                        "INSERT OR IGNORE INTO lease_devices VALUES (?,?)",
                        (str(lease.lease_id), str(t)),
                    )
                self._conn.commit()
            except Exception:
                self._conn.rollback()
                raise

    def release(self, lease: ResourceLease | str) -> None:
        lid = lease if isinstance(lease, str) else str(getattr(lease, "lease_id", ""))
        with self._lock:
            self._conn.execute("DELETE FROM lease_devices WHERE lease_id=?", (lid,))
            self._conn.execute("DELETE FROM leases WHERE lease_id=?", (lid,))
            self._conn.commit()

    def active_leases(self) -> tuple[ResourceLease, ...]:
        rows = self._conn.execute("SELECT * FROM leases").fetchall()
        results = []
        for r in rows:
            dev_rows = self._conn.execute(
                "SELECT token FROM lease_devices WHERE lease_id=?", (r[0],)
            ).fetchall()
            l = ResourceLease(
                lease_id=r[0], owner_id=r[1], scope=r[2], threads=r[3], backend=r[4],
                device_tokens=tuple(d[0] for d in dev_rows),
                policy=ResourcePolicy(**json.loads(r[6])),
                parent_lease_id=r[7], ttl_seconds=r[8], heartbeat_interval_seconds=r[9],
                acquired_at=r[10], last_heartbeat_at=r[11],
                metadata=json.loads(r[12]),
            )
            results.append(l)
        return tuple(results)

    def heartbeat(self, lease_id: str) -> ResourceLease | None:
        with self._lock:
            self._conn.execute(
                "UPDATE leases SET last_heartbeat_at=? WHERE lease_id=?",
                (_now_unix(), str(lease_id)),
            )
        rows = self._conn.execute("SELECT * FROM leases WHERE lease_id=?", (str(lease_id),)).fetchall()
        if not rows:
            return None
        r = rows[0]
        dev_rows = self._conn.execute("SELECT token FROM lease_devices WHERE lease_id=?", (r[0],)).fetchall()
        return ResourceLease(
            lease_id=r[0], owner_id=r[1], scope=r[2], threads=r[3], backend=r[4],
            device_tokens=tuple(d[0] for d in dev_rows),
            policy=ResourcePolicy(**json.loads(r[6])),
            parent_lease_id=r[7], ttl_seconds=r[8], heartbeat_interval_seconds=r[9],
            acquired_at=r[10], last_heartbeat_at=r[11],
            metadata=json.loads(r[12]),
        )

    def prune_expired(self) -> int:
        removed = 0
        with self._lock:
            rows = self._conn.execute("SELECT lease_id, last_heartbeat_at, ttl_seconds FROM leases").fetchall()
            for lid, lhb, ttl in rows:
                if ttl is not None and (_now_unix() - float(lhb)) >= float(ttl):
                    self._conn.execute("DELETE FROM lease_devices WHERE lease_id=?", (lid,))
                    self._conn.execute("DELETE FROM leases WHERE lease_id=?", (lid,))
                    removed += 1
        return removed
