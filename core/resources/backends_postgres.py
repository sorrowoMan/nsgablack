"""PostgreSQL L0 backends for task queue, result, state, and worker registry.

These backends use ``psycopg`` (the same driver as ``catalog/store/postgres.py``)
and auto-create their tables on first use."""

from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from typing import Any, Dict, Mapping, Optional

try:
    from psycopg import connect as _pg_connect
    from psycopg.rows import dict_row as _pg_dict_row
except Exception:  # pragma: no cover - optional dependency
    _pg_connect = None
    _pg_dict_row = None

from .backends import (
    ArtifactBackend,
    ArtifactDataTransportBackend,
    DataTransportBackend,
    FilesystemArtifactBackend,
    L0RuntimeBackend,
    TaskQueueBackend,
    TaskResultBackend,
    TaskStateBackend,
    WorkerRegistryBackend,
    task_from_json,
    task_to_json,
    result_from_json,
    result_to_json,
    infer_task_run_id,
    infer_result_run_id,
)
from .model import TaskEnvelope, TaskResult, WorkerDescriptor

_POSTGRES_SCHEMA_VERSION = 1


def _to_timestamptz(unix_s: float) -> datetime:
    return datetime.fromtimestamp(unix_s, tz=timezone.utc)


def _pg_connect_dict(url: str):
    if _pg_connect is None:
        raise RuntimeError("PostgreSQL L0 backend requires psycopg. Install: pip install psycopg")
    return _pg_connect(str(url), row_factory=_pg_dict_row)


# ── table helpers ────────────────────────────────────────────────────


def _ensure_l0_schema(conn, namespace: str) -> None:
    """Create the L0 schema tables if they don't exist."""
    cur = conn.cursor()
    ns = str(namespace or "nsgablack_l0").strip().lower().replace(":", "_").replace("-", "_")
    cur.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {ns}_schema_version (
            version INTEGER PRIMARY KEY,
            applied_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    cur.execute(f"SELECT version FROM {ns}_schema_version ORDER BY version DESC LIMIT 1")
    row = cur.fetchone()
    applied_version = int(row["version"] if isinstance(row, dict) else (row[0] if row else 0))

    migrations = [
        (
            1,
            (
                f"""
                CREATE TABLE IF NOT EXISTS {ns}_task_queue (
                    id BIGSERIAL PRIMARY KEY,
                    queue_key VARCHAR(512) NOT NULL,
                    payload_json TEXT NOT NULL,
                    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
                )
                """,
                f"CREATE INDEX IF NOT EXISTS idx_{ns}_tq_key ON {ns}_task_queue (queue_key)",
                f"""
                CREATE TABLE IF NOT EXISTS {ns}_task_result (
                    run_id VARCHAR(256) NOT NULL,
                    task_id VARCHAR(256) NOT NULL,
                    payload_json TEXT NOT NULL,
                    completed_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (run_id, task_id)
                )
                """,
                f"CREATE INDEX IF NOT EXISTS idx_{ns}_tr_task ON {ns}_task_result (task_id)",
                f"""
                CREATE TABLE IF NOT EXISTS {ns}_task_state (
                    task_id VARCHAR(256) PRIMARY KEY,
                    state_json TEXT NOT NULL,
                    expires_at TIMESTAMPTZ
                )
                """,
                f"CREATE INDEX IF NOT EXISTS idx_{ns}_ts_expires ON {ns}_task_state (expires_at)",
                f"""
                CREATE TABLE IF NOT EXISTS {ns}_worker_registry (
                    worker_id VARCHAR(256) PRIMARY KEY,
                    descriptor_json TEXT NOT NULL,
                    heartbeat_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
                    heartbeat_json TEXT,
                    expires_at TIMESTAMPTZ
                )
                """,
                f"CREATE INDEX IF NOT EXISTS idx_{ns}_wr_expires ON {ns}_worker_registry (expires_at)",
            ),
        ),
    ]

    for version, statements in migrations:
        if version <= applied_version:
            continue
        for stmt in statements:
            cur.execute(stmt)
        cur.execute(
            f"INSERT INTO {ns}_schema_version (version) VALUES (%s) ON CONFLICT (version) DO NOTHING",
            (version,),
        )
        conn.commit()

    cur.close()


def _table_prefix(namespace: str) -> str:
    return str(namespace or "nsgablack_l0").strip().lower().replace(":", "_").replace("-", "_")


# ── PostgreSQL backends ──────────────────────────────────────────────


class PostgresTaskQueueBackend(TaskQueueBackend):
    """PostgreSQL-backed task queue using ``FOR UPDATE SKIP LOCKED``.

    Producers ``submit()`` to the table; consumers ``claim()`` with row-level
    locking so multiple workers can safely dequeue in parallel without a
    dedicated message broker.
    """

    def __init__(
        self,
        *,
        pg_url: str = "postgresql://127.0.0.1:5432/postgres",
        namespace: str = "nsgablack_l0",
        queue_scope: str = "global",
    ) -> None:
        self.pg_url = str(pg_url)
        self.namespace = str(namespace or "nsgablack_l0").strip().lower().replace(":", "_").replace("-", "_")
        self.queue_scope = str(queue_scope or "global").strip().lower()
        if self.queue_scope not in {"global", "run"}:
            raise ValueError("queue_scope must be 'global' or 'run'")
        self._ensure_tables()

    def _ensure_tables(self) -> None:
        conn = _pg_connect_dict(self.pg_url)
        try:
            _ensure_l0_schema(conn, self.namespace)
        finally:
            conn.close()

    def _queue_key(self, run_id: Optional[str] = None) -> str:
        prefix = _table_prefix(self.namespace)
        if self.queue_scope == "run":
            if not run_id:
                raise ValueError("run_id is required when queue_scope='run'")
            return f"{prefix}:run:{run_id}"
        return f"{prefix}:global"

    def submit(self, task: TaskEnvelope) -> None:
        conn = _pg_connect_dict(self.pg_url)
        try:
            cur = conn.cursor()
            cur.execute(
                f"INSERT INTO {_table_prefix(self.namespace)}_task_queue (queue_key, payload_json) VALUES (%s, %s)",
                (self._queue_key(infer_task_run_id(task)), task_to_json(task)),
            )
            conn.commit()
            cur.close()
        finally:
            conn.close()

    def submit_many(self, tasks: list[TaskEnvelope]) -> None:
        if not tasks:
            return
        conn = _pg_connect_dict(self.pg_url)
        try:
            cur = conn.cursor()
            rows = [(self._queue_key(infer_task_run_id(t)), task_to_json(t)) for t in tasks]
            cur.executemany(
                f"INSERT INTO {_table_prefix(self.namespace)}_task_queue (queue_key, payload_json) VALUES (%s, %s)",
                rows,
            )
            conn.commit()
            cur.close()
        finally:
            conn.close()

    def claim(self, run_id: Optional[str] = None, *, timeout_seconds: int = 1) -> Optional[TaskEnvelope]:
        deadline = time.time() + max(0.1, float(timeout_seconds))
        qk = self._queue_key(run_id)
        tbl = f"{_table_prefix(self.namespace)}_task_queue"
        while time.time() < deadline:
            conn = _pg_connect_dict(self.pg_url)
            try:
                cur = conn.cursor()
                cur.execute(
                    f"SELECT id, payload_json FROM {tbl} WHERE queue_key = %s "
                    "ORDER BY id LIMIT 1 FOR UPDATE SKIP LOCKED",
                    (qk,),
                )
                row = cur.fetchone()
                if row is not None:
                    row_id = int(row["id"]) if isinstance(row, dict) else int(row[0])
                    payload = str(row["payload_json"]) if isinstance(row, dict) else str(row[1])
                    cur.execute(f"DELETE FROM {tbl} WHERE id = %s", (row_id,))
                    conn.commit()
                    cur.close()
                    return task_from_json(payload)
                conn.rollback()
                cur.close()
            finally:
                conn.close()
        return None


class PostgresTaskResultBackend(TaskResultBackend):
    """PostgreSQL-backed task result store."""

    def __init__(
        self,
        *,
        pg_url: str = "postgresql://127.0.0.1:5432/postgres",
        namespace: str = "nsgablack_l0",
    ) -> None:
        self.pg_url = str(pg_url)
        self.namespace = str(namespace or "nsgablack_l0").strip().lower().replace(":", "_").replace("-", "_")
        self._ensure_tables()

    def _ensure_tables(self) -> None:
        conn = _pg_connect_dict(self.pg_url)
        try:
            _ensure_l0_schema(conn, self.namespace)
        finally:
            conn.close()

    def complete(self, result: TaskResult) -> None:
        conn = _pg_connect_dict(self.pg_url)
        try:
            cur = conn.cursor()
            cur.execute(
                f"INSERT INTO {_table_prefix(self.namespace)}_task_result (run_id, task_id, payload_json) "
                "VALUES (%s, %s, %s) ON CONFLICT (run_id, task_id) DO UPDATE SET payload_json = EXCLUDED.payload_json, completed_at = CURRENT_TIMESTAMP",
                (infer_result_run_id(result), result.task_id, result_to_json(result)),
            )
            conn.commit()
            cur.close()
        finally:
            conn.close()

    def get_result(self, run_id: str, task_id: str) -> Optional[TaskResult]:
        conn = _pg_connect_dict(self.pg_url)
        try:
            cur = conn.cursor()
            cur.execute(
                f"SELECT payload_json FROM {_table_prefix(self.namespace)}_task_result WHERE run_id = %s AND task_id = %s",
                (str(run_id), str(task_id)),
            )
            row = cur.fetchone()
            cur.close()
            if row is None:
                return None
            raw = str(row["payload_json"]) if isinstance(row, dict) else str(row[0])
            return result_from_json(raw)
        finally:
            conn.close()


class PostgresTaskStateBackend(TaskStateBackend):
    """PostgreSQL-backed task state with optional TTL."""

    def __init__(
        self,
        *,
        pg_url: str = "postgresql://127.0.0.1:5432/postgres",
        namespace: str = "nsgablack_l0",
    ) -> None:
        self.pg_url = str(pg_url)
        self.namespace = str(namespace or "nsgablack_l0").strip().lower().replace(":", "_").replace("-", "_")
        self._ensure_tables()

    def _ensure_tables(self) -> None:
        conn = _pg_connect_dict(self.pg_url)
        try:
            _ensure_l0_schema(conn, self.namespace)
        finally:
            conn.close()

    def set_task_state(self, task_id: str, state: Mapping[str, Any], *, ttl_seconds: Optional[float] = None) -> None:
        expires = None
        if ttl_seconds is not None and float(ttl_seconds) > 0:
            expires = _to_timestamptz(time.time() + float(ttl_seconds))
        conn = _pg_connect_dict(self.pg_url)
        try:
            cur = conn.cursor()
            self._sweep(conn, cur)
            cur.execute(
                f"INSERT INTO {_table_prefix(self.namespace)}_task_state (task_id, state_json, expires_at) "
                "VALUES (%s, %s, %s) ON CONFLICT (task_id) DO UPDATE SET state_json = EXCLUDED.state_json, expires_at = EXCLUDED.expires_at",
                (str(task_id), json.dumps(dict(state), ensure_ascii=False), expires),
            )
            conn.commit()
            cur.close()
        finally:
            conn.close()

    def get_task_state(self, task_id: str) -> Optional[Dict[str, Any]]:
        conn = _pg_connect_dict(self.pg_url)
        try:
            cur = conn.cursor()
            self._sweep(conn, cur)
            cur.execute(
                f"SELECT state_json FROM {_table_prefix(self.namespace)}_task_state WHERE task_id = %s",
                (str(task_id),),
            )
            row = cur.fetchone()
            cur.close()
            if row is None:
                return None
            raw = str(row["state_json"]) if isinstance(row, dict) else str(row[0])
            value = json.loads(raw)
            return dict(value) if isinstance(value, Mapping) else {}
        finally:
            conn.close()

    def delete_task_state(self, task_id: str) -> None:
        conn = _pg_connect_dict(self.pg_url)
        try:
            cur = conn.cursor()
            cur.execute(
                f"DELETE FROM {_table_prefix(self.namespace)}_task_state WHERE task_id = %s",
                (str(task_id),),
            )
            conn.commit()
            cur.close()
        finally:
            conn.close()

    def _sweep(self, conn, cur) -> None:
        cur.execute(
            f"DELETE FROM {_table_prefix(self.namespace)}_task_state WHERE expires_at IS NOT NULL AND expires_at <= CURRENT_TIMESTAMP"
        )


class PostgresWorkerRegistryBackend(WorkerRegistryBackend):
    """PostgreSQL-backed worker registry with heartbeat TTL."""

    def __init__(
        self,
        *,
        pg_url: str = "postgresql://127.0.0.1:5432/postgres",
        namespace: str = "nsgablack_l0",
    ) -> None:
        self.pg_url = str(pg_url)
        self.namespace = str(namespace or "nsgablack_l0").strip().lower().replace(":", "_").replace("-", "_")
        self._ensure_tables()

    def _ensure_tables(self) -> None:
        conn = _pg_connect_dict(self.pg_url)
        try:
            _ensure_l0_schema(conn, self.namespace)
        finally:
            conn.close()

    def register(self, worker: WorkerDescriptor | Mapping[str, Any], *, ttl_seconds: Optional[float] = None) -> None:
        item = worker if isinstance(worker, WorkerDescriptor) else WorkerDescriptor.from_dict(worker)
        expires = None
        if ttl_seconds is not None and float(ttl_seconds) > 0:
            expires = _to_timestamptz(time.time() + float(ttl_seconds))
        conn = _pg_connect_dict(self.pg_url)
        try:
            cur = conn.cursor()
            self._sweep(conn, cur)
            cur.execute(
                f"INSERT INTO {_table_prefix(self.namespace)}_worker_registry "
                "(worker_id, descriptor_json, expires_at) VALUES (%s, %s, %s) "
                "ON CONFLICT (worker_id) DO UPDATE SET descriptor_json = EXCLUDED.descriptor_json, expires_at = EXCLUDED.expires_at",
                (str(item.worker_id), json.dumps(item.as_dict(), ensure_ascii=False), expires),
            )
            conn.commit()
            cur.close()
        finally:
            conn.close()

    def heartbeat(self, worker_id: str, payload: Optional[Mapping[str, Any]] = None, *, ttl_seconds: int = 30) -> None:
        expires = _to_timestamptz(time.time() + int(ttl_seconds))
        heartbeat_data = json.dumps(
            {"worker_id": str(worker_id), "time": time.time(), "payload": dict(payload or {})},
            ensure_ascii=False,
        )
        conn = _pg_connect_dict(self.pg_url)
        try:
            cur = conn.cursor()
            self._sweep(conn, cur)
            cur.execute(
                f"INSERT INTO {_table_prefix(self.namespace)}_worker_registry "
                "(worker_id, descriptor_json, heartbeat_at, heartbeat_json, expires_at) "
                "VALUES (%s, %s, CURRENT_TIMESTAMP, %s, %s) "
                "ON CONFLICT (worker_id) DO UPDATE SET heartbeat_at = CURRENT_TIMESTAMP, heartbeat_json = EXCLUDED.heartbeat_json, expires_at = EXCLUDED.expires_at",
                (str(worker_id), "{}", heartbeat_data, expires),
            )
            conn.commit()
            cur.close()
        finally:
            conn.close()

    def get_worker(self, worker_id: str) -> Optional[WorkerDescriptor]:
        conn = _pg_connect_dict(self.pg_url)
        try:
            cur = conn.cursor()
            self._sweep(conn, cur)
            cur.execute(
                f"SELECT descriptor_json FROM {_table_prefix(self.namespace)}_worker_registry WHERE worker_id = %s",
                (str(worker_id),),
            )
            row = cur.fetchone()
            cur.close()
            if row is None:
                return None
            raw = str(row["descriptor_json"]) if isinstance(row, dict) else str(row[0])
            return WorkerDescriptor.from_dict(json.loads(raw))
        finally:
            conn.close()

    def list_workers(self) -> list[WorkerDescriptor]:
        """Return all non-expired registered workers."""
        conn = _pg_connect_dict(self.pg_url)
        try:
            cur = conn.cursor()
            self._sweep(conn, cur)
            cur.execute(
                f"SELECT descriptor_json FROM {_table_prefix(self.namespace)}_worker_registry "
                "WHERE (expires_at IS NULL OR expires_at > CURRENT_TIMESTAMP)"
            )
            rows = cur.fetchall() or []
            cur.close()
            out: list[WorkerDescriptor] = []
            for row in rows:
                raw = str(row["descriptor_json"]) if isinstance(row, dict) else str(row[0])
                out.append(WorkerDescriptor.from_dict(json.loads(raw)))
            return out
        finally:
            conn.close()

    def _sweep(self, conn, cur) -> None:
        cur.execute(
            f"DELETE FROM {_table_prefix(self.namespace)}_worker_registry WHERE expires_at IS NOT NULL AND expires_at <= CURRENT_TIMESTAMP"
        )


# ── composite backend ────────────────────────────────────────────────


class PostgresL0RuntimeBackend(L0RuntimeBackend):
    """Composite PostgreSQL-backed L0 runtime.

    Usage::

        backend = PostgresL0RuntimeBackend(pg_url="postgresql://127.0.0.1:5432/postgres")
        backend.submit(task_envelope)
        claimed = backend.claim(run_id="demo")

    All five sub-backends (queue, result, state, worker registry, artifact)
    are backed by a single PostgreSQL database.  Data transport uses inline
    JSON for small payloads; for large artefacts, swap ``artifact_backend``
    to ``FilesystemArtifactBackend`` or an S3-backed implementation.
    """

    def __init__(
        self,
        *,
        pg_url: str = "postgresql://127.0.0.1:5432/postgres",
        namespace: str = "nsgablack_l0",
        queue_scope: str = "global",
        artifact_backend: Optional[ArtifactBackend] = None,
        data_transport: Optional[DataTransportBackend] = None,
    ) -> None:
        queue = PostgresTaskQueueBackend(pg_url=pg_url, namespace=namespace, queue_scope=queue_scope)
        result = PostgresTaskResultBackend(pg_url=pg_url, namespace=namespace)
        state = PostgresTaskStateBackend(pg_url=pg_url, namespace=namespace)
        workers = PostgresWorkerRegistryBackend(pg_url=pg_url, namespace=namespace)

        if artifact_backend is None:
            artifact_backend = FilesystemArtifactBackend()
        if data_transport is None:
            data_transport = ArtifactDataTransportBackend(artifact_backend)

        super().__init__(
            task_queue=queue,
            result_backend=result,
            worker_registry=workers,
            state_backend=state,
            artifact_backend=artifact_backend,
            data_transport=data_transport,
        )
        self._pg_url = str(pg_url)
        self._namespace = str(namespace)

    @property
    def namespace(self) -> str:
        return str(getattr(self.task_queue, "namespace", self._namespace))

    @property
    def queue_scope(self) -> str:
        return str(getattr(self.task_queue, "queue_scope", "global"))
