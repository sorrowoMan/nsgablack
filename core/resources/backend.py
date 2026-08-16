"""
L0 Runtime Backend implementations.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from blackbase.resources import (
    TaskEnvelope,
    TaskResult,
    WorkerDescriptor,
)


class L0RuntimeBackend(ABC):
    """Abstract base class for L0 runtime backends."""
    
    @abstractmethod
    def submit(self, envelope: TaskEnvelope) -> None:
        pass
    
    @abstractmethod
    def claim(self, run_id: str) -> Optional[TaskEnvelope]:
        pass
    
    @abstractmethod
    def complete(self, task_id: str, result: TaskResult) -> None:
        pass
    
    @abstractmethod
    def get_result(self, task_id: str) -> Optional[TaskResult]:
        pass
    
    @abstractmethod
    def register_worker(self, worker: WorkerDescriptor) -> None:
        pass
    
    @abstractmethod
    def unregister_worker(self, worker_id: str) -> None:
        pass
    
    @abstractmethod
    def shutdown(self) -> None:
        pass


class InMemoryL0RuntimeBackend(L0RuntimeBackend):
    """In-memory L0 runtime backend."""
    
    def __init__(self):
        self._tasks: Dict[str, TaskEnvelope] = {}
        self._results: Dict[str, TaskResult] = {}
        self._workers: Dict[str, WorkerDescriptor] = {}
        self._claimed: Dict[str, str] = {}  # task_id -> worker_id
    
    def submit(self, envelope: TaskEnvelope) -> None:
        self._tasks[envelope.task_id] = envelope
    
    def claim(self, run_id: str) -> Optional[TaskEnvelope]:
        for task_id, envelope in list(self._tasks.items()):
            if task_id not in self._claimed:
                self._claimed[task_id] = run_id
                return envelope
        return None
    
    def complete(self, task_id: str, result: TaskResult) -> None:
        self._results[task_id] = result
        self._claimed.pop(task_id, None)
    
    def get_result(self, task_id: str) -> Optional[TaskResult]:
        return self._results.get(task_id)
    
    def register_worker(self, worker: WorkerDescriptor) -> None:
        self._workers[worker.worker_id] = worker
    
    def unregister_worker(self, worker_id: str) -> None:
        self._workers.pop(worker_id, None)
    
    def shutdown(self) -> None:
        self._tasks.clear()
        self._results.clear()
        self._workers.clear()
        self._claimed.clear()


class RedisL0RuntimeBackend(L0RuntimeBackend):
    """Redis-based L0 runtime backend."""
    
    def __init__(self, redis_url: str = "redis://127.0.0.1:6379/0"):
        self._redis_url = redis_url
        self._client = None
    
    def _connect(self):
        if self._client is None:
            try:
                import redis
                self._client = redis.from_url(self._redis_url)
            except ImportError:
                raise ImportError("redis package is required for RedisL0RuntimeBackend")
    
    def submit(self, envelope: TaskEnvelope) -> None:
        self._connect()
        import json
        self._client.set(f"task:{envelope.task_id}", json.dumps(envelope.to_dict()))
    
    def claim(self, run_id: str) -> Optional[TaskEnvelope]:
        self._connect()
        import json
        for key in self._client.keys("task:*"):
            task_id = key.decode().replace("task:", "")
            if not self._client.get(f"claimed:{task_id}"):
                self._client.set(f"claimed:{task_id}", run_id)
                data = self._client.get(key)
                if data:
                    return TaskEnvelope.from_dict(json.loads(data))
        return None
    
    def complete(self, task_id: str, result: TaskResult) -> None:
        self._connect()
        import json
        self._client.set(f"result:{task_id}", json.dumps(result.to_dict()))
        self._client.delete(f"claimed:{task_id}")
    
    def get_result(self, task_id: str) -> Optional[TaskResult]:
        self._connect()
        import json
        data = self._client.get(f"result:{task_id}")
        if data:
            return TaskResult.from_dict(json.loads(data))
        return None
    
    def register_worker(self, worker: WorkerDescriptor) -> None:
        self._connect()
        import json
        self._client.set(f"worker:{worker.worker_id}", json.dumps(worker.to_dict()))
    
    def unregister_worker(self, worker_id: str) -> None:
        self._connect()
        self._client.delete(f"worker:{worker_id}")
    
    def shutdown(self) -> None:
        if self._client:
            self._client.close()
            self._client = None


class PostgresL0RuntimeBackend(L0RuntimeBackend):
    """PostgreSQL-based L0 runtime backend."""
    
    def __init__(self, pg_url: str = "postgresql://127.0.0.1:5432/postgres"):
        self._pg_url = pg_url
        self._conn = None
    
    def _connect(self):
        if self._conn is None:
            try:
                import psycopg2
                self._conn = psycopg2.connect(self._pg_url)
            except ImportError:
                raise ImportError("psycopg2 package is required for PostgresL0RuntimeBackend")
    
    def submit(self, envelope: TaskEnvelope) -> None:
        self._connect()
        import json
        with self._conn.cursor() as cur:
            cur.execute(
                "INSERT INTO tasks (task_id, data) VALUES (%s, %s)",
                (envelope.task_id, json.dumps(envelope.to_dict()))
            )
            self._conn.commit()
    
    def claim(self, run_id: str) -> Optional[TaskEnvelope]:
        self._connect()
        import json
        with self._conn.cursor() as cur:
            cur.execute(
                "SELECT task_id, data FROM tasks WHERE claimed_by IS NULL LIMIT 1 FOR UPDATE",
            )
            row = cur.fetchone()
            if row:
                task_id, data = row
                cur.execute(
                    "UPDATE tasks SET claimed_by = %s WHERE task_id = %s",
                    (run_id, task_id)
                )
                self._conn.commit()
                return TaskEnvelope.from_dict(json.loads(data))
        return None
    
    def complete(self, task_id: str, result: TaskResult) -> None:
        self._connect()
        import json
        with self._conn.cursor() as cur:
            cur.execute(
                "INSERT INTO results (task_id, data) VALUES (%s, %s)",
                (task_id, json.dumps(result.to_dict()))
            )
            cur.execute(
                "UPDATE tasks SET claimed_by = NULL WHERE task_id = %s",
                (task_id,)
            )
            self._conn.commit()
    
    def get_result(self, task_id: str) -> Optional[TaskResult]:
        self._connect()
        import json
        with self._conn.cursor() as cur:
            cur.execute(
                "SELECT data FROM results WHERE task_id = %s",
                (task_id,)
            )
            row = cur.fetchone()
            if row:
                return TaskResult.from_dict(json.loads(row[0]))
        return None
    
    def register_worker(self, worker: WorkerDescriptor) -> None:
        self._connect()
        import json
        with self._conn.cursor() as cur:
            cur.execute(
                "INSERT INTO workers (worker_id, data) VALUES (%s, %s) ON CONFLICT (worker_id) DO UPDATE SET data = EXCLUDED.data",
                (worker.worker_id, json.dumps(worker.to_dict()))
            )
            self._conn.commit()
    
    def unregister_worker(self, worker_id: str) -> None:
        self._connect()
        with self._conn.cursor() as cur:
            cur.execute("DELETE FROM workers WHERE worker_id = %s", (worker_id,))
            self._conn.commit()
    
    def shutdown(self) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None


__all__ = [
    "L0RuntimeBackend",
    "InMemoryL0RuntimeBackend",
    "RedisL0RuntimeBackend",
    "PostgresL0RuntimeBackend",
]