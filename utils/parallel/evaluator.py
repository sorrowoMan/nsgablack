"""Parallel population evaluation utilities (engineering module).

This module accelerates problem evaluation (and optional constraints/bias)
by running population evaluation in parallel.

Backends
- process: ProcessPoolExecutor (CPU-bound; requires picklable task config)
- thread: ThreadPoolExecutor (I/O / numpy-heavy; affected by GIL for pure Python)
- joblib: optional joblib-based parallelism
- ray: optional Ray distributed backend (strongly recommend problem_factory)
"""

from __future__ import annotations

import copy
import os
import pickle
import time
import warnings
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor, as_completed
from multiprocessing import cpu_count
from typing import Any, Callable, Dict, List, Literal, Optional, Tuple, Union

import numpy as np

from ...bias import BiasModule
from ...core.base import BlackBoxProblem
from ..constraints.constraint_utils import evaluate_constraints_safe
from ..context.context_keys import (
    KEY_BOUNDS,
    KEY_CONSTRAINT_VIOLATION,
    KEY_PROBLEM,
)
from ..context.context_schema import build_minimal_context

Backend = Literal["process", "thread", "ray", "joblib"]

ProblemFactory = Callable[[], BlackBoxProblem]
ContextBuilder = Callable[
    [np.ndarray, int, BlackBoxProblem, np.ndarray, float, Dict[str, Any]],
    Dict[str, Any],
]


def _is_picklable(obj: Any) -> Tuple[bool, Optional[str]]:
    try:
        pickle.dumps(obj)
        return True, None
    except Exception as exc:
        return False, repr(exc)


def _default_context_builder(
    individual: np.ndarray,
    idx: int,
    problem: BlackBoxProblem,
    constraints: np.ndarray,
    violation: float,
    extra_context: Dict[str, Any],
) -> Dict[str, Any]:
    ctx = build_minimal_context(
        generation=extra_context.get("generation"),
        individual_id=idx,
        constraints=constraints.tolist() if getattr(constraints, "size", 0) > 0 else [],
        constraint_violation=float(violation),
        seed=extra_context.get("seed"),
        metadata=extra_context.get("metadata"),
        extra=extra_context,
    )
    # Keep a reference for bias implementations that need the problem (thread backend only).
    ctx[KEY_PROBLEM] = problem
    try:
        ctx.setdefault(KEY_BOUNDS, getattr(problem, "bounds", None))
    except Exception:
        pass
    return ctx


def _evaluate_individual_task_static(
    task_args: Tuple[np.ndarray, int, Dict[str, Any]]
) -> Tuple[int, np.ndarray, float, Optional[str]]:
    """Picklable evaluation task (ProcessPool/joblib/Ray)."""

    individual, idx, config = task_args
    enable_bias = bool(config.get("enable_bias", False))
    bias_module = config.get("bias_module", None)
    bias_module_factory = config.get("bias_module_factory", None)
    if enable_bias and callable(bias_module_factory):
        try:
            bias_module = bias_module_factory()
        except Exception as exc:
            return idx, np.full(1, np.inf), float("inf"), f"bias_module_factory failed: {exc!r}"
    num_objectives = int(config.get("num_objectives", 1) or 1)

    problem = config.get("problem", None)
    problem_factory = config.get("problem_factory", None)
    if problem is None and callable(problem_factory):
        problem = problem_factory()

    if problem is None:
        return idx, np.full(num_objectives, np.inf), float("inf"), "No problem provided"

    context_builder = config.get("context_builder", None) or _default_context_builder
    extra_context = config.get("extra_context", None) or {}

    try:
        val = problem.evaluate(individual)
        obj = np.asarray(val, dtype=float).flatten()

        cons_arr, violation = evaluate_constraints_safe(problem, individual)
        context = context_builder(individual, idx, problem, cons_arr, float(violation), dict(extra_context))

        if enable_bias and bias_module is not None:
            if num_objectives == 1:
                f_biased = bias_module.compute_bias(individual, float(obj[0]), idx, context=context)
                obj = np.array([f_biased], dtype=float)
            else:
                if callable(getattr(bias_module, "compute_bias_vector", None)):
                    obj = np.asarray(
                        bias_module.compute_bias_vector(individual, obj, idx, context=context),
                        dtype=float,
                    ).reshape(-1)
                else:
                    obj_biased = []
                    for j in range(len(obj)):
                        f_biased = bias_module.compute_bias(individual, float(obj[j]), idx, context=context)
                        obj_biased.append(f_biased)
                    obj = np.asarray(obj_biased, dtype=float).reshape(-1)

        if cons_arr.size == 0 and KEY_CONSTRAINT_VIOLATION in context:
            violation = float(context[KEY_CONSTRAINT_VIOLATION])

        return idx, obj, float(violation), None
    except Exception as exc:
        return idx, np.full(num_objectives, np.inf), float("inf"), repr(exc)


def _ray_evaluate_individual_task(task_args: Tuple[np.ndarray, int, Dict[str, Any]]):
    """Top-level helper for Ray remote execution (cloudpickle-friendly)."""

    return _evaluate_individual_task_static(task_args)


class ParallelEvaluator:
    """Population evaluator with switchable parallel backends."""

    def __init__(
        self,
        backend: Backend = "process",
        max_workers: Optional[int] = None,
        chunk_size: Optional[int] = None,
        enable_load_balancing: bool = True,
        retry_errors: bool = True,
        max_retries: int = 3,
        verbose: bool = False,
        *,
        precheck: bool = True,
        strict: bool = False,
        fallback_backend: Backend = "thread",
        problem_factory: Optional[ProblemFactory] = None,
        context_builder: Optional[ContextBuilder] = None,
        extra_context: Optional[Dict[str, Any]] = None,
        thread_bias_isolation: Literal["deepcopy", "disable_cache", "off"] = "deepcopy",
    ) -> None:
        self.backend: Backend = backend
        self.max_workers = int(max_workers or self._get_default_workers(backend))
        self.chunk_size = chunk_size
        self.enable_load_balancing = bool(enable_load_balancing)
        self.retry_errors = bool(retry_errors)
        self.max_retries = int(max_retries)
        self.verbose = bool(verbose)

        self.precheck = bool(precheck)
        self.strict = bool(strict)
        self.fallback_backend: Backend = fallback_backend
        self.problem_factory = problem_factory
        self.context_builder = context_builder
        self.extra_context: Dict[str, Any] = dict(extra_context or {})
        self.thread_bias_isolation: Literal["deepcopy", "disable_cache", "off"] = thread_bias_isolation

        self.stats: Dict[str, Any] = {
            "total_evaluations": 0,
            "total_time": 0.0,
            "avg_evaluation_time": 0.0,
            "error_count": 0,
            "retry_count": 0,
        }

        self._executor: Optional[Any] = None

    def _get_default_workers(self, backend: Backend) -> int:
        if backend == "process":
            return min(cpu_count(), 8)
        if backend == "thread":
            return min(cpu_count() * 2, 16)
        return max(1, cpu_count())

    def _create_executor(self):
        if self._executor is not None:
            return self._executor

        if self.backend == "process":
            self._executor = ProcessPoolExecutor(max_workers=self.max_workers)
        elif self.backend == "thread":
            self._executor = ThreadPoolExecutor(max_workers=self.max_workers)
        elif self.backend == "ray":
            # no executor; just ensure ray is ready
            try:
                import ray  # type: ignore

                if not ray.is_initialized():
                    ray.init(ignore_reinit_error=True, include_dashboard=False, log_to_driver=False)
                self._executor = None
            except Exception as exc:
                warnings.warn(f"Ray backend unavailable ({exc!r}), falling back to process backend")
                self.backend = "process"
                self._executor = ProcessPoolExecutor(max_workers=self.max_workers)
        elif self.backend == "joblib":
            self._executor = None

        return self._executor

    def _evaluate_individual_task(
        self, task_args: Tuple[np.ndarray, int, Dict[str, Any]]
    ) -> Tuple[int, np.ndarray, float, Optional[str]]:
        return _evaluate_individual_task_static(task_args)

    def _precheck_or_fallback(self, task_config: Dict[str, Any]) -> None:
        if not self.precheck:
            return

        if self.backend == "process":
            ok, err = _is_picklable(task_config)
            if ok:
                return
            msg = (
                f"process backend requires picklable task_config; got error: {err}. "
                "Consider backend='thread' or providing problem_factory/context_builder as top-level callables."
            )
            if self.strict:
                raise ValueError(msg)
            warnings.warn(msg)
            self.backend = self.fallback_backend
            self._executor = None
            return

        if self.backend == "ray":
            # Ray uses cloudpickle; best-effort check if cloudpickle is available.
            try:
                import cloudpickle  # type: ignore

                cloudpickle.dumps(task_config)
                return
            except Exception as exc:
                msg = f"ray backend requires cloudpickle-serializable task_config; got error: {exc!r}"
                if self.strict:
                    raise ValueError(msg)
                warnings.warn(msg)
                self.backend = self.fallback_backend
                self._executor = None

    def evaluate_population(
        self,
        population: np.ndarray,
        problem: BlackBoxProblem,
        enable_bias: bool = False,
        bias_module: Optional[BiasModule] = None,
        return_detailed: bool = False,
    ) -> Union[Tuple[np.ndarray, np.ndarray], Dict[str, Any]]:
        start_time = time.time()
        restore_cache_enabled: Optional[bool] = None

        population = np.asarray(population)
        if population.ndim == 1:
            population = population.reshape(1, -1)

        pop_size = int(population.shape[0])
        num_objectives = 1 if problem.get_num_objectives() is None else int(problem.get_num_objectives())

        objectives = np.full((pop_size, num_objectives), np.inf)
        constraint_violations = np.full(pop_size, np.inf)

        task_config: Dict[str, Any] = {
            "enable_bias": bool(enable_bias),
            "bias_module": bias_module,
            "num_objectives": int(num_objectives),
            "context_builder": self.context_builder,
            "extra_context": dict(self.extra_context),
        }

        # Thread backend isolation guard:
        # - deepcopy: each task gets an isolated bias module clone
        # - disable_cache: shared module but force cache off for this evaluation call
        # - off: keep existing behavior
        if self.backend == "thread" and bool(enable_bias) and bias_module is not None:
            mode = str(self.thread_bias_isolation or "deepcopy").strip().lower()
            if mode not in ("deepcopy", "disable_cache", "off"):
                msg = (
                    f"invalid thread_bias_isolation={self.thread_bias_isolation!r}; "
                    "expected one of: deepcopy/disable_cache/off"
                )
                if self.strict:
                    raise ValueError(msg)
                warnings.warn(msg)
                mode = "deepcopy"
            if mode == "deepcopy":
                task_config["bias_module"] = None
                task_config["bias_module_factory"] = lambda bm=bias_module: copy.deepcopy(bm)
            elif mode == "disable_cache":
                if hasattr(bias_module, "cache_enabled"):
                    try:
                        restore_cache_enabled = bool(getattr(bias_module, "cache_enabled"))
                        setattr(bias_module, "cache_enabled", False)
                    except Exception:
                        restore_cache_enabled = None

        if self.backend in ("process", "ray") and callable(self.problem_factory):
            task_config["problem_factory"] = self.problem_factory
        else:
            if self.backend == "ray":
                msg = (
                    "backend='ray' strongly recommends providing problem_factory "
                    "(construct problem inside worker)."
                )
                if self.strict:
                    raise ValueError(msg)
                warnings.warn(msg)
            task_config["problem"] = problem

        self._precheck_or_fallback(task_config)

        tasks = [(population[i], i, task_config) for i in range(pop_size)]
        if self.verbose:
            print(f"[parallel] start n={pop_size} backend={self.backend} workers={self.max_workers}")

        error_count = 0
        error_samples: List[str] = []
        try:
            if self.backend == "ray":
                results = self._evaluate_with_ray(tasks)
            elif self.backend == "joblib":
                results = self._evaluate_with_joblib(tasks)
            else:
                results = self._evaluate_with_executor(tasks)

            for idx, obj, violation, error in results:
                if error is None:
                    objectives[idx] = obj
                    constraint_violations[idx] = float(violation)
                else:
                    error_count += 1
                    self.stats["error_count"] += 1
                    if error is not None and len(error_samples) < 5:
                        error_samples.append(f"idx={idx} err={error}")
                    if self.retry_errors and self.max_retries > 0:
                        objectives[idx], constraint_violations[idx] = self._retry_evaluation(
                            population[idx], idx, task_config
                        )
        except Exception as exc:
            warnings.warn(f"Parallel evaluation failed; falling back to serial: {exc!r}")
            return self._evaluate_serial(population, problem, enable_bias, bias_module, return_detailed)
        finally:
            if (
                restore_cache_enabled is not None
                and bias_module is not None
                and hasattr(bias_module, "cache_enabled")
            ):
                try:
                    setattr(bias_module, "cache_enabled", bool(restore_cache_enabled))
                except Exception:
                    pass
            if self._executor is not None and hasattr(self._executor, "shutdown"):
                try:
                    self._executor.shutdown(wait=False)
                finally:
                    self._executor = None

        total_time = max(0.0, float(time.time() - start_time))
        self.stats["total_evaluations"] = int(self.stats["total_evaluations"]) + pop_size
        self.stats["total_time"] = float(self.stats["total_time"]) + total_time
        self.stats["avg_evaluation_time"] = float(total_time) / float(max(1, pop_size))

        if self.verbose:
            print(f"[parallel] done elapsed={total_time:.2f}s avg_ms={total_time/pop_size*1000:.2f}")
            if error_count > 0:
                print(f"[parallel] warning: {error_count} individuals failed")

        if self.strict and error_count > 0:
            detail = "; ".join(error_samples) if error_samples else "no error detail captured"
            raise RuntimeError(f"Parallel evaluation failed for {error_count}/{pop_size}. Sample errors: {detail}")

        if return_detailed:
            return {
                "objectives": objectives,
                "constraint_violations": constraint_violations,
                "evaluation_time": total_time,
                "stats": dict(self.stats),
                "error_count": int(error_count),
                "success_rate": float(pop_size - error_count) / float(max(1, pop_size)),
            }
        return objectives, constraint_violations

    def _evaluate_with_executor(self, tasks: List[Tuple]) -> List[Tuple]:
        executor = self._create_executor()
        if executor is None:
            # ray/joblib should not reach here
            raise RuntimeError(f"No executor for backend={self.backend}")

        task_func = _evaluate_individual_task_static if self.backend == "process" else self._evaluate_individual_task

        if self.enable_load_balancing:
            futures = {executor.submit(task_func, task): int(task[1]) for task in tasks}
            results: List[Tuple] = []
            for future in as_completed(futures):
                idx = futures[future]
                try:
                    results.append(future.result(timeout=30))
                except Exception as exc:
                    results.append((idx, np.full(1, np.inf), float("inf"), repr(exc)))
            return results

        results = []
        for result in executor.map(task_func, tasks, timeout=30):
            results.append(result)
        return results

    def _evaluate_with_ray(self, tasks: List[Tuple]) -> List[Tuple]:
        try:
            import ray  # type: ignore
        except Exception as exc:  # pragma: no cover
            warnings.warn(f"Ray not installed ({exc!r}), falling back to process backend")
            self.backend = "process"
            self._executor = None
            return self._evaluate_with_executor(tasks)

        if not ray.is_initialized():
            ray.init(ignore_reinit_error=True, include_dashboard=False, log_to_driver=False)

        remote_fn = ray.remote(_ray_evaluate_individual_task)
        refs = []
        ref_to_idx: Dict[Any, int] = {}
        for task in tasks:
            ref = remote_fn.remote(task)
            refs.append(ref)
            ref_to_idx[ref] = int(task[1])

        results: List[Tuple] = []
        pending = list(refs)
        while pending:
            ready, pending = ray.wait(pending, num_returns=min(256, len(pending)), timeout=30.0)
            if not ready:
                for ref in pending:
                    idx = int(ref_to_idx.get(ref, -1))
                    results.append((idx, np.full(1, np.inf), float("inf"), "ray.wait timeout"))
                break
            for ref in ready:
                idx = int(ref_to_idx.get(ref, -1))
                try:
                    results.append(ray.get(ref))
                except Exception as exc:
                    results.append((idx, np.full(1, np.inf), float("inf"), repr(exc)))
        return results

    def _evaluate_with_joblib(self, tasks: List[Tuple]) -> List[Tuple]:
        """Evaluate tasks using joblib (optional dependency)."""

        try:
            from joblib import Parallel, delayed  # type: ignore
        except Exception as exc:  # pragma: no cover
            raise ImportError("Joblib not installed. Install with: pip install joblib") from exc

        results = Parallel(
            n_jobs=self.max_workers,
            backend="multiprocessing" if self.backend == "process" else "threading",
            verbose=5 if self.verbose else 0,
            batch_size=self.chunk_size or "auto",
        )(delayed(_evaluate_individual_task_static)(task) for task in tasks)
        return list(results)

    def _retry_evaluation(self, individual: np.ndarray, idx: int, config: Dict[str, Any]) -> Tuple[np.ndarray, float]:
        for attempt in range(self.max_retries):
            try:
                _, obj, violation, error = self._evaluate_individual_task((individual, idx, config))
                if error is None:
                    self.stats["retry_count"] += 1
                    if self.verbose:
                        print(f"[parallel] retry success idx={idx} attempt={attempt + 1}")
                    return obj, float(violation)
            except Exception:
                continue

        warnings.warn(f"[parallel] idx={idx} failed after {self.max_retries} retries")
        return np.full(1, np.inf), float("inf")

    def _evaluate_serial(
        self,
        population: np.ndarray,
        problem: BlackBoxProblem,
        enable_bias: bool = False,
        bias_module: Optional[BiasModule] = None,
        return_detailed: bool = False,
    ) -> Union[Tuple[np.ndarray, np.ndarray], Dict[str, Any]]:
        pop = np.asarray(population)
        if pop.ndim == 1:
            pop = pop.reshape(1, -1)
        pop_size = int(pop.shape[0])
        num_objectives = 1 if problem.get_num_objectives() is None else int(problem.get_num_objectives())

        objectives = np.full((pop_size, num_objectives), np.inf)
        constraint_violations = np.full(pop_size, np.inf)

        for i in range(pop_size):
            _, obj, violation, _ = _evaluate_individual_task_static(
                (
                    pop[i],
                    i,
                    {
                        "problem": problem,
                        "enable_bias": bool(enable_bias),
                        "bias_module": bias_module,
                        "num_objectives": int(num_objectives),
                    },
                )
            )
            objectives[i] = obj
            constraint_violations[i] = float(violation)

        if return_detailed:
            return {
                "objectives": objectives,
                "constraint_violations": constraint_violations,
                "evaluation_time": 0.0,
                "stats": dict(self.stats),
                "error_count": 0,
                "success_rate": 1.0,
            }
        return objectives, constraint_violations

    def get_stats(self) -> Dict[str, Any]:
        return dict(self.stats)

    def reset_stats(self) -> None:
        self.stats = {
            "total_evaluations": 0,
            "total_time": 0.0,
            "avg_evaluation_time": 0.0,
            "error_count": 0,
            "retry_count": 0,
        }

    def estimate_speedup(self, population_size: int, avg_eval_time: float) -> float:
        # Simple Amdahl-style estimate (heuristic).
        if self.max_workers <= 1:
            return 1.0
        serial_fraction = 0.1
        parallel_fraction = 1.0 - serial_fraction
        theoretical = 1.0 / (serial_fraction + parallel_fraction / float(self.max_workers))
        if population_size < self.max_workers * 2:
            theoretical *= float(population_size) / float(self.max_workers * 2)
        return float(min(theoretical, float(self.max_workers)))

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self._executor is not None and hasattr(self._executor, "shutdown"):
            self._executor.shutdown(wait=True)
            self._executor = None


def create_parallel_evaluator(backend: Backend = "process", max_workers: Optional[int] = None, **kwargs) -> ParallelEvaluator:
    return ParallelEvaluator(backend=backend, max_workers=max_workers, **kwargs)


class SmartEvaluatorSelector:
    """Heuristics to choose a default evaluator configuration."""

    @staticmethod
    def select_evaluator(
        problem: BlackBoxProblem,
        population_size: int,
        environment: Optional[Dict[str, Any]] = None,
    ) -> ParallelEvaluator:
        env = dict(environment or {})
        cpu = int(env.get("cpu_count", os.cpu_count() or 1))

        problem_type = SmartEvaluatorSelector._analyze_problem_type(problem)

        if problem_type.get("io_intensive"):
            backend: Backend = "thread"
            max_workers = min(cpu * 2, 16)
        elif problem_type.get("memory_intensive"):
            backend = "joblib"
            max_workers = max(1, cpu // 2)
        else:
            backend = "process"
            max_workers = min(cpu, 8)

        if population_size < 10:
            max_workers = min(max_workers, 2)
            chunk_size: Optional[int] = 1
        elif population_size > 100:
            chunk_size = max(1, int(population_size // max(1, max_workers * 2)))
        else:
            chunk_size = None

        return ParallelEvaluator(
            backend=backend,
            max_workers=max_workers,
            chunk_size=chunk_size,
            enable_load_balancing=bool(population_size > 20),
            verbose=False,
        )

    @staticmethod
    def _analyze_problem_type(problem: BlackBoxProblem) -> Dict[str, bool]:
        # Conservative defaults: treat as CPU-bound unless proven otherwise.
        return {
            "cpu_intensive": True,
            "io_intensive": False,
            "memory_intensive": False,
            "has_constraints": bool(hasattr(problem, "evaluate_constraints")),
            "is_multi_objective": bool(problem.get_num_objectives() and problem.get_num_objectives() > 1),
        }
