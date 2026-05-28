from __future__ import annotations

import threading
import time

import numpy as np

from nsgablack.core.resources import RedisL0RuntimeBackend, ResourceRequirement, TaskEnvelope, TaskResult
from nsgablack.utils.parallel import (
    RedisNestedDistributedEvaluator,
    run_nested_redis_worker_once,
)


class _FakePipeline:
    def __init__(self, client):
        self.client = client
        self.ops = []

    def rpush(self, key, value):
        self.ops.append(("rpush", key, value))
        return self

    def execute(self):
        for op, key, value in self.ops:
            if op == "rpush":
                self.client.rpush(key, value)
        return [1 for _ in self.ops]


class _FakeRedis:
    def __init__(self):
        self._lists = {}
        self._values = {}
        self._cond = threading.Condition()

    def pipeline(self, transaction=False):
        _ = transaction
        return _FakePipeline(self)

    def rpush(self, key, value):
        with self._cond:
            self._lists.setdefault(str(key), []).append(value)
            self._cond.notify_all()
        return 1

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


def test_redis_l0_backend_uses_task_envelope_and_task_result(tmp_path):
    queue = RedisL0RuntimeBackend(
        client=_FakeRedis(),
        namespace="test:nested",
        result_ttl_seconds=None,
        artifact_base_dir=tmp_path,
    )
    task = TaskEnvelope(
        task_id="t1",
        task_type="nested_candidate_eval",
        payload={"run_id": "r1", "index": 0, "candidate": [1.0]},
        requirement=ResourceRequirement(capabilities=("nested_eval",)),
        namespace="r1",
    )

    queue.submit(task)
    claimed = queue.claim(timeout_seconds=1)
    assert isinstance(claimed, TaskEnvelope)
    assert claimed.task_id == task.task_id
    assert claimed.payload["candidate"] == [1.0]

    result = TaskResult(
        task_id=task.task_id,
        status="ok",
        objectives=(1.0,),
        violations=(0.0,),
        metadata={"run_id": "r1", "index": 0},
    )
    queue.complete(result)
    restored = queue.get_result("r1", "t1")
    assert isinstance(restored, TaskResult)
    assert restored.objectives == (1.0,)
    assert restored.violations == (0.0,)


def test_redis_nested_distributed_evaluator_uses_external_worker_loop_with_l0_protocol(tmp_path):
    queue = RedisL0RuntimeBackend(client=_FakeRedis(), namespace="test:nested:evaluator", artifact_base_dir=tmp_path)
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

    def task_runner(task: TaskEnvelope):
        candidate = np.asarray(task.payload["candidate"], dtype=float)
        total = float(np.sum(candidate))
        return TaskResult(
            task_id=task.task_id,
            status="ok",
            objectives=(total, float(task.payload["index"])),
            violations=(0.0,),
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
    assert len(evaluator.last_task_results) == int(population.shape[0])
    for item in evaluator.last_task_results:
        assert item["lease_id"]
        assert item["resource_context"]["lease"]["lease_id"] == item["lease_id"]
        assert item["resource_context"]["task_id"] == item["task_id"]
