from __future__ import annotations

import threading
import time

import numpy as np

from blackbase.resources import (
    RedisTaskRuntimeBackend,
    ResourceContext,
    ResourceRequirement,
    TaskEnvelope,
    TaskResult,
    WorkerDescriptor,
)
from nsgablack.utils.parallel import (
    RedisNestedDistributedEvaluator,
    run_nested_redis_worker_once,
)


class _FakePipeline:
    def __init__(self, client):
        self.client = client
        self.ops = []

    def __getattr__(self, name):
        def enqueue(*args):
            self.ops.append((name, args))
            return self

        return enqueue

    def execute(self):
        with self.client._cond:
            return [getattr(self.client, name)(*args) for name, args in self.ops]


class _FakeLock:
    def __init__(self, lock):
        self.lock = lock

    def acquire(self, blocking=True):
        return self.lock.acquire(blocking=blocking)

    def release(self):
        self.lock.release()


class _FakeRedis:
    def __init__(self):
        self._lists = {}
        self._values = {}
        self._sets = {}
        self._locks = {}
        self._cond = threading.Condition()

    def pipeline(self, transaction=False):
        _ = transaction
        return _FakePipeline(self)

    def lock(self, name, timeout=None, blocking_timeout=None):
        _ = timeout, blocking_timeout
        with self._cond:
            lock = self._locks.setdefault(str(name), threading.RLock())
        return _FakeLock(lock)

    def rpush(self, key, value):
        with self._cond:
            self._lists.setdefault(str(key), []).append(value)
            self._cond.notify_all()
        return 1

    def lrange(self, key, start, end):
        with self._cond:
            values = list(self._lists.get(str(key), []))
        stop = len(values) if int(end) == -1 else int(end) + 1
        return values[int(start):stop]

    def lrem(self, key, count, value):
        with self._cond:
            values = self._lists.setdefault(str(key), [])
            limit = abs(int(count))
            removed = 0
            output = []
            for item in values:
                if item == value and (limit == 0 or removed < limit):
                    removed += 1
                else:
                    output.append(item)
            self._lists[str(key)] = output
            return removed

    def sadd(self, key, *values):
        with self._cond:
            target = self._sets.setdefault(str(key), set())
            before = len(target)
            target.update(values)
            return len(target) - before

    def srem(self, key, *values):
        with self._cond:
            target = self._sets.setdefault(str(key), set())
            before = len(target)
            target.difference_update(values)
            return before - len(target)

    def smembers(self, key):
        with self._cond:
            return set(self._sets.get(str(key), set()))

    def blpop(self, key, timeout=1):
        key = str(key)
        deadline = time.time() + float(timeout)
        with self._cond:
            while True:
                items = self._lists.get(key, [])
                if items:
                    return key, items.pop(0)
                remaining = deadline - time.time()
                if remaining <= 0:
                    return None
                self._cond.wait(timeout=min(remaining, 0.05))

    def set(self, key, value):
        with self._cond:
            self._values[str(key)] = value
            self._cond.notify_all()
        return True

    def setex(self, key, ttl, value):
        _ = ttl
        return self.set(key, value)

    def get(self, key):
        with self._cond:
            return self._values.get(str(key))

    def delete(self, key):
        with self._cond:
            return int(self._values.pop(str(key), None) is not None)


def test_redis_task_runtime_uses_task_envelope_and_task_result():
    queue = RedisTaskRuntimeBackend(
        client=_FakeRedis(),
        namespace="test:nested",
    )
    task = TaskEnvelope(
        task_id="t1",
        task_type="nested_candidate_eval",
        payload={"run_id": "r1", "index": 0, "candidate": [1.0]},
        requirement=ResourceRequirement(capabilities=("nested_eval",)),
        namespace="r1",
    )

    queue.submit(task)
    worker = WorkerDescriptor(
        worker_id="worker-a",
        executor_backend="thread",
        capabilities=("nested_eval",),
        offer={"threads": 1, "gpus": 0, "backend": "local"},
    )
    claimed = queue.claim_task(worker, run_id="r1", timeout_seconds=1)
    assert claimed is not None
    assert claimed.task.task_id == task.task_id
    assert claimed.task.payload["candidate"] == (1.0,)

    result = TaskResult(
        task_id=task.task_id,
        status="ok",
        objectives=(1.0,),
        violations=(0.0,),
        metadata={"run_id": "r1", "index": 0},
    )
    queue.complete_claim(claimed, result)
    restored = queue.get_result("r1", "t1")
    assert isinstance(restored, TaskResult)
    assert restored.objectives == (1.0,)
    assert restored.violations == (0.0,)


def test_redis_nested_distributed_evaluator_uses_external_worker_loop_with_l0_protocol():
    queue = RedisTaskRuntimeBackend(client=_FakeRedis(), namespace="test:nested:evaluator")
    evaluator = RedisNestedDistributedEvaluator(
        queue=queue,
        run_id="case42",
        timeout_seconds=5.0,
        poll_interval_seconds=0.01,
    )
    population = np.array([[1.0, 2.0], [3.0, 4.0], [5.0, 6.0]], dtype=float)

    class _Problem:
        name = "fake"

    class _Solver:
        problem = _Problem()
        num_objectives = 2
        generation = 7
        _resource_context_explicit = True
        resource_context = ResourceContext.from_mapping(
            {
                "threads": 1,
                "namespace": "project.outer",
            "grant": {
                "threads": 1,
                "workers": 1,
                "capabilities": ["nested_eval"],
            },
                "lease": {"lease_id": "project-lease", "owner_id": "outer"},
            }
        )

        @classmethod
        def get_resource_context(cls):
            return cls.resource_context

    seen_resource_contexts = []
    def task_runner(task: TaskEnvelope):
        candidate = np.asarray(task.payload["candidate"], dtype=float)
        total = float(np.sum(candidate))
        seen_resource_contexts.append(dict(task.payload["resource_context"]))
        return TaskResult(
            task_id=task.task_id,
            status="ok",
            objectives=(total, float(task.payload["index"])),
            violations=(0.0,),
            resource_context=dict(task.payload["resource_context"]),
            metadata={
                "run_id": task.payload["run_id"],
                "index": task.payload["index"],
                "generation": task.payload["generation"],
            },
        )

    def worker_loop():
        for _ in range(int(population.shape[0])):
            assert run_nested_redis_worker_once(
                queue=queue,
                task_runner=task_runner,
                claim_timeout_seconds=1,
            )

    worker = threading.Thread(target=worker_loop, daemon=True)
    worker.start()
    objectives, violations = evaluator.evaluate_population(_Solver(), population)
    worker.join(timeout=2.0)

    assert np.allclose(objectives, [[3.0, 0.0], [7.0, 1.0], [11.0, 2.0]])
    assert np.allclose(violations, [0.0, 0.0, 0.0])
    assert len(seen_resource_contexts) == int(population.shape[0])
    assert all(item["lease"]["lease_id"] != "project-lease" for item in seen_resource_contexts)
    assert len(evaluator.last_task_results) == int(population.shape[0])
    for item in evaluator.last_task_results:
        assert item["lease_id"]
        assert item["resource_context"]["lease"]["lease_id"] == item["lease_id"]
        assert item["resource_context"]["task_id"] == item["task_id"]
        assert item["metadata"]["parent_lease_id"] == "project-lease"
