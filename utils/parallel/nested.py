"""Nested-runtime aware parallel population evaluation.

This evaluator is intentionally different from the generic ParallelEvaluator:
it preserves solver-level nested semantics by invoking the problem's
inner_runtime_evaluator instead of calling problem.evaluate() directly.
"""

from __future__ import annotations

import copy
import threading
import time
from concurrent.futures import ThreadPoolExecutor, wait
from typing import Any, Dict, Optional, Tuple
from uuid import uuid4

import numpy as np

from ...core.nested_solver import InnerRuntimeEvaluator
from ...core.resources import (
    InMemoryResourceScheduler,
    L0RuntimeBackend,
    ResourceRequirement,
    TaskEnvelope,
    TaskResult,
    WorkerDescriptor,
    build_local_worker_descriptor,
)
from ...utils.constraints.constraint_utils import evaluate_constraints_safe
from ...utils.extension_contracts import normalize_objectives, normalize_violation


class _PluginManagerProxy:
    def __init__(self, plugin_manager: Any, lock: threading.RLock) -> None:
        self._plugin_manager = plugin_manager
        self._lock = lock

    def dispatch(self, event_name: str, *args: Any, **kwargs: Any) -> Any:
        with self._lock:
            return self._plugin_manager.dispatch(event_name, *args, **kwargs)

    def list_plugins(self, enabled_only: bool = False) -> list:
        list_plugins = getattr(self._plugin_manager, "list_plugins", None)
        if callable(list_plugins):
            with self._lock:
                return list_plugins(enabled_only=enabled_only)
        return []


class _NestedWorkerSolverProxy:
    def __init__(self, parent: Any, plugin_manager: _PluginManagerProxy) -> None:
        self._parent = parent
        self.problem = getattr(parent, "problem", None)
        self.plugin_manager = plugin_manager
        self.generation = int(getattr(parent, "generation", 0))
        self.num_objectives = int(getattr(parent, "num_objectives", 1) or 1)
        self.enable_bias = False
        self.bias_module = None
        self.evaluation_mediator = getattr(parent, "evaluation_mediator", None)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._parent, name)


def _clone_evaluator(evaluator: Any) -> Any:
    try:
        return copy.deepcopy(evaluator)
    except Exception:
        try:
            cloned = copy.copy(evaluator)
            if hasattr(cloned, "stats"):
                cloned.stats = dict(getattr(evaluator, "stats", {}) or {})
            return cloned
        except Exception:
            return evaluator


def _build_nested_task_envelope(
    solver: Any,
    x: np.ndarray,
    idx: int,
    *,
    run_id: str,
    task_id: Optional[str] = None,
    executor_backend: str = "thread",
    metadata: Optional[Dict[str, Any]] = None,
) -> TaskEnvelope:
    n_obj = int(getattr(solver, "num_objectives", 1) or 1)
    problem = getattr(solver, "problem", None)
    generation = int(getattr(solver, "generation", 0))
    candidate = np.asarray(x, dtype=float).reshape(-1).tolist()
    task_meta = {
        "generation": generation,
        "num_objectives": n_obj,
        "problem_name": str(getattr(problem, "name", "")),
        "source": "nsgablack.nested_runtime",
    }
    if metadata:
        task_meta.update(dict(metadata))
    requirement = _resolve_nested_task_requirement(solver)
    return TaskEnvelope(
        task_id=str(task_id or f"task_{uuid4().hex[:16]}"),
        task_type="nested_candidate_eval",
        payload={
            "candidate": candidate,
            "index": int(idx),
            "run_id": str(run_id),
            "generation": generation,
            "num_objectives": n_obj,
            "problem_name": str(getattr(problem, "name", "")),
        },
        requirement=requirement,
        executor_backend=str(executor_backend or "thread"),
        namespace=str(run_id),
        metadata=task_meta,
    )


def _resolve_nested_task_requirement(solver: Any) -> ResourceRequirement:
    problem = getattr(solver, "problem", None)
    raw = None
    for owner in (solver, problem):
        if owner is None:
            continue
        for name in ("outer_task_requirement", "nested_task_requirement", "outer_resource_requirement"):
            raw = getattr(owner, name, None)
            if raw is not None:
                break
        if raw is not None:
            break
    if isinstance(raw, ResourceRequirement):
        base = raw
    elif isinstance(raw, dict):
        base = ResourceRequirement.from_dict(raw)
    else:
        base = ResourceRequirement(threads=1, capabilities=("nested_eval",))
    caps = tuple(dict.fromkeys(tuple(base.capabilities) + ("nested_eval",)))
    metadata = dict(base.metadata)
    metadata.setdefault("source", "nsgablack.nested_runtime")
    return ResourceRequirement(
        threads=int(base.threads),
        gpus=int(base.gpus),
        resource_backend=str(base.resource_backend),
        device_tokens=tuple(base.device_tokens),
        memory_mb=base.memory_mb,
        gpu_memory_mb=base.gpu_memory_mb,
        capabilities=caps,
        timeout_seconds=base.timeout_seconds,
        metadata=metadata,
    )


def _task_candidate(task: TaskEnvelope) -> np.ndarray:
    return np.asarray(dict(task.payload).get("candidate", []), dtype=float).reshape(-1)


def _task_index(task: TaskEnvelope) -> int:
    payload = dict(task.payload)
    if "index" in payload:
        return int(payload["index"])
    return int(dict(task.metadata).get("index", 0))


def _task_result_violation(result: TaskResult) -> float:
    if result.violations:
        return float(result.violations[0])
    return float(dict(result.metrics).get("violation", 0.0))


def _task_run_id(task: TaskEnvelope) -> str:
    payload = dict(task.payload)
    return str(payload.get("run_id") or task.namespace or "default")


def _attach_task_metadata_to_result(result: TaskResult, task: TaskEnvelope, *, worker_id: str = "") -> TaskResult:
    payload = dict(task.payload)
    metadata = dict(result.metadata)
    metadata.setdefault("run_id", _task_run_id(task))
    metadata.setdefault("index", int(payload.get("index", 0)))
    metadata.setdefault("generation", payload.get("generation"))
    metadata.setdefault("task_type", str(task.task_type))
    merged_resource_context = dict(result.resource_context or {})
    merged_resource_context.setdefault("run_id", _task_run_id(task))
    merged_resource_context.setdefault("task_id", str(task.task_id))
    return TaskResult(
        task_id=str(result.task_id or task.task_id),
        status=str(result.status),
        objectives=tuple(result.objectives),
        violations=tuple(result.violations),
        metrics=dict(result.metrics),
        artifact_refs=tuple(result.artifact_refs),
        worker_id=str(result.worker_id or worker_id),
        lease_id=str(result.lease_id),
        resource_context=merged_resource_context,
        error=str(result.error or ""),
        started_at=float(result.started_at),
        finished_at=float(result.finished_at),
        metadata=metadata,
    )


class NestedParallelEvaluator:
    """Threaded evaluator for problem.inner_runtime_evaluator workloads."""

    def __init__(
        self,
        *,
        max_workers: Optional[int] = None,
        strict: bool = False,
        verbose: bool = False,
        task_timeout_seconds: Optional[float] = None,
    ) -> None:
        self.max_workers = int(max_workers or 1)
        self.strict = bool(strict)
        self.verbose = bool(verbose)
        self.task_timeout_seconds = None if task_timeout_seconds is None else float(task_timeout_seconds)
        self.stats: Dict[str, Any] = {
            "total_evaluations": 0,
            "total_time": 0.0,
            "error_count": 0,
            "timeout_count": 0,
        }
        self.last_run_id: str = ""
        self.last_task_results: list[Dict[str, Any]] = []
        self._plugin_lock = threading.RLock()

    def evaluate_population(self, solver: Any, population: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        problem = getattr(solver, "problem", None)
        evaluator = getattr(problem, "inner_runtime_evaluator", None) if problem is not None else None
        if not callable(getattr(evaluator, "evaluate", None)):
            raise RuntimeError("NestedParallelEvaluator requires problem.inner_runtime_evaluator.evaluate")
        if not isinstance(evaluator, InnerRuntimeEvaluator):
            raise RuntimeError("NestedParallelEvaluator only supports InnerRuntimeEvaluator instances")

        pop = np.asarray(population, dtype=float)
        if pop.ndim == 1:
            pop = pop.reshape(1, -1)
        n = int(pop.shape[0])
        n_obj = int(getattr(solver, "num_objectives", 1) or 1)
        objectives = np.full((n, n_obj), np.inf, dtype=float)
        violations = np.full((n,), np.inf, dtype=float)

        start = time.time()
        errors: list[str] = []
        workers = max(1, min(int(self.max_workers), n))
        if self.verbose:
            print(f"[nested-parallel] start n={n} workers={workers}")

        run_id = f"thread_nested_{uuid4().hex[:8]}"
        self.last_run_id = run_id
        self.last_task_results = []
        tasks = [
            _build_nested_task_envelope(
                solver,
                pop[i],
                i,
                run_id=run_id,
                executor_backend="thread",
            )
            for i in range(n)
        ]
        scheduler = InMemoryResourceScheduler(
            workers=(
                WorkerDescriptor(
                    worker_id=f"{run_id}:local-thread",
                    executor_backend="thread",
                    resource_backend="local",
                    capabilities=("nested_eval", "cpu", "numpy"),
                    offer={"threads": workers, "gpus": 0, "metadata": {"executor": "thread"}},
                    max_inflight=workers,
                ),
            )
        )
        pool = ThreadPoolExecutor(max_workers=workers)
        try:
            futures = {pool.submit(self._evaluate_task, solver, evaluator, tasks[i], scheduler): i for i in range(n)}
            done, pending = wait(
                futures,
                timeout=self.task_timeout_seconds,
            )
            for future in done:
                idx = int(futures[future])
                try:
                    result = future.result()
                    if not isinstance(result, TaskResult):
                        raise TypeError("nested thread task did not return TaskResult")
                    self.last_task_results.append(result.as_dict())
                    if not result.ok:
                        raise RuntimeError(result.error or "nested thread task failed")
                    objectives[idx] = normalize_objectives(
                        result.objectives,
                        num_objectives=n_obj,
                        name="nested_parallel.task_result.objectives",
                    )
                    violations[idx] = normalize_violation(
                        _task_result_violation(result),
                        name="nested_parallel.task_result.violation",
                    )
                except Exception as exc:
                    errors.append(f"idx={idx} err={exc!r}")
                    if self.strict:
                        raise
                    objectives[idx] = np.full((n_obj,), np.inf, dtype=float)
                    violations[idx] = float("inf")
            for future in pending:
                idx = int(futures[future])
                errors.append(f"idx={idx} err=TimeoutError('nested evaluation task timeout')")
                future.cancel()
                failure = TaskResult.failure(
                    task_id=str(tasks[idx].task_id),
                    error="TimeoutError: nested evaluation task timeout",
                    worker_id=f"{run_id}:local-thread",
                )
                self.last_task_results.append(_attach_task_metadata_to_result(failure, tasks[idx]).as_dict())
                if self.strict:
                    raise TimeoutError(f"nested evaluation task timeout for idx={idx}")
                objectives[idx] = np.full((n_obj,), np.inf, dtype=float)
                violations[idx] = float("inf")
        finally:
            pool.shutdown(wait=False, cancel_futures=True)

        elapsed = max(0.0, float(time.time() - start))
        self.stats["total_evaluations"] = int(self.stats.get("total_evaluations", 0)) + n
        self.stats["total_time"] = float(self.stats.get("total_time", 0.0)) + elapsed
        self.stats["error_count"] = int(self.stats.get("error_count", 0)) + len(errors)
        self.stats["timeout_count"] = int(self.stats.get("timeout_count", 0)) + sum("timeout" in item.lower() for item in errors)
        if self.verbose:
            print(f"[nested-parallel] done elapsed={elapsed:.2f}s errors={len(errors)}")
            for item in errors[:5]:
                print(f"[nested-parallel] {item}")
        return objectives, violations

    def _evaluate_task(
        self,
        solver: Any,
        evaluator: Any,
        task: TaskEnvelope,
        scheduler: InMemoryResourceScheduler,
    ) -> TaskResult:
        scheduled = scheduler.acquire(task, owner_id=str(task.task_id), scope=str(task.task_type))
        plugin_proxy = _PluginManagerProxy(getattr(solver, "plugin_manager"), self._plugin_lock)
        worker_solver = _NestedWorkerSolverProxy(solver, plugin_proxy)
        local_evaluator = _clone_evaluator(evaluator)
        x = _task_candidate(task)
        idx = _task_index(task)
        try:
            nested = local_evaluator.evaluate(
                solver=worker_solver,
                x=x,
                individual_id=int(idx),
                context={
                    "individual_id": int(idx),
                    "task_id": str(task.task_id),
                    "l0_task": task.as_dict(),
                    "resource_context": dict(scheduled.resource_context),
                },
            )
            if nested is None:
                raise RuntimeError("inner_runtime_evaluator returned None")

            obj_raw, vio_raw = nested
            obj = normalize_objectives(
                obj_raw,
                num_objectives=int(getattr(solver, "num_objectives", 1) or 1),
                name="nested_parallel.objectives",
            )
            vio = normalize_violation(vio_raw, name="nested_parallel.violation")

            cons_arr, violation_calc = evaluate_constraints_safe(
                getattr(solver, "problem", None),
                x,
            )
            _ = cons_arr
            if np.isfinite(float(violation_calc)):
                vio = float(max(float(vio), float(violation_calc)))
            return TaskResult.success(
                task_id=str(task.task_id),
                objectives=tuple(float(v) for v in obj),
                violations=(float(vio),),
                worker_id=str(scheduled.worker.worker_id),
                lease_id=str(scheduled.lease.lease_id),
                resource_context=dict(scheduled.resource_context),
                metrics={
                    "index": int(idx),
                    "generation": int(getattr(solver, "generation", 0)),
                    "executor_backend": "thread",
                },
            )
        finally:
            scheduler.release(scheduled)

class RedisNestedDistributedEvaluator:
    """Submit nested evaluation tasks to Redis and collect worker results.

    Workers are external: they claim tasks from Redis, run the case-local nested
    task, and call queue.complete(...). This evaluator intentionally does not
    execute candidates locally.
    """

    def __init__(
        self,
        *,
        queue: L0RuntimeBackend,
        run_id: Optional[str] = None,
        timeout_seconds: float = 3600.0,
        poll_interval_seconds: float = 1.0,
        strict: bool = False,
        verbose: bool = False,
    ) -> None:
        self.queue = queue
        self.run_id = str(run_id or f"nested_{uuid4().hex[:12]}")
        self.timeout_seconds = float(timeout_seconds)
        self.poll_interval_seconds = float(poll_interval_seconds)
        self.strict = bool(strict)
        self.verbose = bool(verbose)
        self.stats: Dict[str, Any] = {
            "submitted": 0,
            "completed": 0,
            "failed": 0,
            "timeout": 0,
        }
        self.last_run_id: str = ""
        self.last_task_results: list[Dict[str, Any]] = []

    def evaluate_population(self, solver: Any, population: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        pop = np.asarray(population, dtype=float)
        if pop.ndim == 1:
            pop = pop.reshape(1, -1)
        n = int(pop.shape[0])
        n_obj = int(getattr(solver, "num_objectives", 1) or 1)
        run_id = f"{self.run_id}_{uuid4().hex[:8]}"
        self.last_run_id = run_id
        self.last_task_results = []
        tasks = [
            _build_nested_task_envelope(
                solver,
                pop[i],
                i,
                run_id=run_id,
                executor_backend="redis",
                metadata={
                    "generation": int(getattr(solver, "generation", 0)),
                    "num_objectives": n_obj,
                    "problem_name": str(getattr(getattr(solver, "problem", None), "name", "")),
                },
            )
            for i in range(n)
        ]
        self.queue.submit_many(tasks)
        self.stats["submitted"] = int(self.stats.get("submitted", 0)) + n
        if self.verbose:
            print(f"[nested-redis] submitted n={n} run_id={run_id}")

        objectives = np.full((n, n_obj), np.inf, dtype=float)
        violations = np.full((n,), np.inf, dtype=float)
        remaining = {task.task_id: task for task in tasks}
        deadline = time.time() + float(self.timeout_seconds)
        while remaining and time.time() < deadline:
            for task_id, task in list(remaining.items()):
                result = self.queue.get_result(run_id, task_id)
                if result is None:
                    continue
                remaining.pop(task_id, None)
                self.last_task_results.append(result.as_dict())
                if result.ok:
                    idx = _task_index(task)
                    objectives[idx] = normalize_objectives(
                        result.objectives,
                        num_objectives=n_obj,
                        name="nested_redis.objectives",
                    )
                    violations[idx] = normalize_violation(
                        _task_result_violation(result),
                        name="nested_redis.violation",
                    )
                    self.stats["completed"] = int(self.stats.get("completed", 0)) + 1
                else:
                    self.stats["failed"] = int(self.stats.get("failed", 0)) + 1
                    if self.strict:
                        raise RuntimeError(f"nested redis task failed: {result.error}")
            if remaining:
                time.sleep(max(0.05, float(self.poll_interval_seconds)))

        if remaining:
            self.stats["timeout"] = int(self.stats.get("timeout", 0)) + len(remaining)
            if self.strict:
                raise TimeoutError(f"nested redis evaluation timed out for {len(remaining)} tasks")
        return objectives, violations


def run_nested_redis_worker_once(
    *,
    queue: L0RuntimeBackend,
    run_id: Optional[str] = None,
    task_runner: Any,
    worker_id: Optional[str] = None,
    claim_timeout_seconds: int = 1,
) -> bool:
    """Run one Redis nested task with a case-provided task_runner.

    task_runner signature: fn(task: TaskEnvelope) -> TaskResult | mapping
    """

    worker = str(worker_id or f"worker_{uuid4().hex[:8]}")
    queue.heartbeat(worker, {"run_id": run_id})
    task = queue.claim(run_id, timeout_seconds=int(claim_timeout_seconds))
    if task is None:
        return False
    scheduler = InMemoryResourceScheduler(
        workers=(
            build_local_worker_descriptor(
                worker_id=worker,
                executor_backend="redis",
                capabilities=("cpu", "numpy", "nested_eval"),
                include_cuda=(
                    int(task.requirement.gpus) > 0
                    or bool(task.requirement.device_tokens)
                    or task.requirement.gpu_memory_mb is not None
                ),
                max_inflight=1,
            ),
        )
    )
    scheduled = None
    try:
        scheduled = scheduler.acquire(task, owner_id=str(worker), scope=str(task.task_type))
        raw = task_runner(task)
        if isinstance(raw, TaskResult):
            result = _attach_task_metadata_to_result(raw, task, worker_id=worker)
        elif isinstance(raw, dict):
            status = str(raw.get("status", "ok" if bool(raw.get("ok", True)) else "failed"))
            result = TaskResult(
                task_id=task.task_id,
                status=status,
                objectives=tuple(float(x) for x in raw.get("objectives", [])),
                violations=(float(raw.get("violation", 0.0)),),
                error=str(raw.get("error", "") or ""),
                worker_id=worker,
                metrics=dict(raw.get("metrics", {}) or {}),
                metadata=dict(raw.get("metadata", {}) or {}),
            )
            result = _attach_task_metadata_to_result(result, task, worker_id=worker)
        else:
            raise TypeError("task_runner must return TaskResult or mapping")
        result = TaskResult(
            task_id=str(result.task_id),
            status=str(result.status),
            objectives=tuple(result.objectives),
            violations=tuple(result.violations),
            metrics=dict(result.metrics),
            artifact_refs=tuple(result.artifact_refs),
            worker_id=str(result.worker_id or worker),
            lease_id=str(result.lease_id or scheduled.lease.lease_id),
            resource_context={**dict(scheduled.resource_context), **dict(result.resource_context or {})},
            error=str(result.error or ""),
            started_at=float(result.started_at),
            finished_at=float(result.finished_at),
            metadata=dict(result.metadata),
        )
    except Exception as exc:
        result = TaskResult.failure(
            task_id=task.task_id,
            error=f"{type(exc).__name__}: {exc}",
            worker_id=worker,
        )
        result = _attach_task_metadata_to_result(result, task, worker_id=worker)
        if scheduled is not None:
            result = TaskResult(
                task_id=str(result.task_id),
                status=str(result.status),
                objectives=tuple(result.objectives),
                violations=tuple(result.violations),
                metrics=dict(result.metrics),
                artifact_refs=tuple(result.artifact_refs),
                worker_id=str(result.worker_id or worker),
                lease_id=str(result.lease_id or scheduled.lease.lease_id),
                resource_context={**dict(scheduled.resource_context), **dict(result.resource_context or {})},
                error=str(result.error or ""),
                started_at=float(result.started_at),
                finished_at=float(result.finished_at),
                metadata=dict(result.metadata),
            )
    finally:
        if scheduled is not None:
            scheduler.release(scheduled)
    queue.complete(result)
    return True


def run_nested_redis_worker(
    *,
    queue: L0RuntimeBackend,
    task_runner: Any,
    worker_id: Optional[str] = None,
    run_id: Optional[str] = None,
    max_tasks: Optional[int] = None,
    idle_timeout_seconds: Optional[float] = None,
    claim_timeout_seconds: int = 1,
) -> Dict[str, Any]:
    """Run a simple blocking Redis nested worker loop.

    This is intentionally framework-level L0 plumbing. Case code supplies
    task_runner so the queue does not know business semantics.
    """

    worker = str(worker_id or f"worker_{uuid4().hex[:8]}")
    processed = 0
    idle_started = time.time()
    while True:
        queue.heartbeat(worker, {"run_id": run_id, "processed": processed})
        did_work = run_nested_redis_worker_once(
            queue=queue,
            run_id=run_id,
            task_runner=task_runner,
            worker_id=worker,
            claim_timeout_seconds=int(claim_timeout_seconds),
        )
        if did_work:
            processed += 1
            idle_started = time.time()
        else:
            if idle_timeout_seconds is not None and time.time() - idle_started >= float(idle_timeout_seconds):
                break
        if max_tasks is not None and processed >= int(max_tasks):
            break
    return {"worker_id": worker, "processed": int(processed)}
