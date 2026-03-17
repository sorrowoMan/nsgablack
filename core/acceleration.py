"""L0 acceleration infrastructure (cross-cutting execution backends)."""

from __future__ import annotations

from concurrent.futures import (
    Future,
    ProcessPoolExecutor,
    ThreadPoolExecutor,
    TimeoutError as FutureTimeoutError,
)
from dataclasses import dataclass, field
import importlib
import pickle
from threading import RLock
import time
from typing import Any, Callable, Dict, Mapping, Optional, Protocol, Tuple


class AccelerationBackend(Protocol):
    """Execution backend contract for acceleration tasks."""

    def run(self, task: str, payload: Mapping[str, Any]) -> Any:
        ...

    def submit(self, task: str, payload: Mapping[str, Any]) -> Any:
        ...


@dataclass
class ExecutionResult:
    """Normalized result returned by acceleration backends."""

    ok: bool
    data: Any = None
    error: Optional[str] = None
    backend: Optional[str] = None
    latency_ms: Optional[float] = None
    trace_id: Optional[str] = None
    metrics: Dict[str, Any] = field(default_factory=dict)


class AccelerationError(RuntimeError):
    """Raised when a strict acceleration task fails."""


class NoopAccelerationBackend:
    """Fallback backend: executes callable payload inline when available."""

    def run(self, task: str, payload: Mapping[str, Any]) -> Any:
        if not isinstance(payload, Mapping):
            raise RuntimeError("payload must be a mapping")
        fn = _resolve_callable(payload)
        if not callable(fn):
            raise RuntimeError(f"NoopAccelerationBackend cannot execute task '{task}' without a callable")

        args = payload.get("args", ())
        kwargs = payload.get("kwargs", {})

        task_name = str(task or "").strip().lower()
        if task_name in {"map", "batch"}:
            items = payload.get("items", None)
            if items is None:
                raise RuntimeError("map task requires payload['items']")
            return [fn(item, *args, **kwargs) for item in list(items)]

        return fn(*args, **kwargs)

    def submit(self, task: str, payload: Mapping[str, Any]) -> Any:
        return self.run(task, payload)


@dataclass(frozen=True)
class BackendKey:
    scope: str
    backend: str


BackendFactory = Callable[..., AccelerationBackend]


class AccelerationRegistry:
    """Registry mapping (scope, backend) -> backend factory."""

    _GLOBAL: "AccelerationRegistry | None" = None

    def __init__(self) -> None:
        self._lock = RLock()
        self._factories: Dict[BackendKey, BackendFactory] = {}

    @classmethod
    def global_registry(cls) -> "AccelerationRegistry":
        if cls._GLOBAL is None:
            cls._GLOBAL = cls()
        return cls._GLOBAL

    def register(self, *, scope: str, backend: str, factory: BackendFactory) -> None:
        key = BackendKey(scope=str(scope).strip().lower(), backend=str(backend).strip().lower())
        if not key.scope or not key.backend:
            raise ValueError("scope/backend must be non-empty")
        if not callable(factory):
            raise TypeError("factory must be callable")
        with self._lock:
            self._factories[key] = factory

    def get(self, *, scope: str, backend: str = "default", **kwargs: Any) -> AccelerationBackend:
        scope_text = str(scope).strip().lower()
        backend_text = str(backend or "default").strip().lower()
        key_exact = BackendKey(scope=scope_text, backend=backend_text)
        key_default = BackendKey(scope=scope_text, backend="default")
        with self._lock:
            factory = self._factories.get(key_exact) or self._factories.get(key_default)
        if factory is None:
            return NoopAccelerationBackend()
        return factory(**kwargs)

    def list_backends(self, *, scope: Optional[str] = None) -> Tuple[BackendKey, ...]:
        with self._lock:
            keys = tuple(self._factories.keys())
        if scope is None:
            return keys
        scope_text = str(scope).strip().lower()
        return tuple(k for k in keys if k.scope == scope_text)


class AccelerationFacade:
    """Runtime-facing accessor for acceleration backends."""

    def __init__(self, registry: Optional[AccelerationRegistry] = None) -> None:
        self._registry = registry or AccelerationRegistry.global_registry()

    def register(self, *, scope: str, backend: str, factory: BackendFactory) -> None:
        self._registry.register(scope=scope, backend=backend, factory=factory)

    def get(self, *, scope: str, backend: str = "default", **kwargs: Any) -> AccelerationBackend:
        return self._registry.get(scope=scope, backend=backend, **kwargs)

    def list_backends(self, *, scope: Optional[str] = None) -> Tuple[BackendKey, ...]:
        return self._registry.list_backends(scope=scope)

    # ------------------------------------------------------------------
    # L0 unified execution API
    # ------------------------------------------------------------------
    def run(
        self,
        *,
        scope: str,
        task: str,
        payload: Optional[Mapping[str, Any]] = None,
        backend: Optional[str],
        hints: Optional[Mapping[str, Any]] = None,
        context: Optional[Mapping[str, Any]] = None,
    ) -> ExecutionResult:
        self._require_backend(backend)
        backend_name = str(backend)
        merged: Dict[str, Any] = dict(payload or {})
        if context is not None:
            merged.setdefault("context", dict(context))
        if hints is not None:
            merged.setdefault("hints", dict(hints))

        runner = self.get(scope=str(scope), backend=backend_name)
        t0 = time.time()
        try:
            raw = runner.run(str(task), merged)
            result = _coerce_result(raw)
        except Exception as exc:
            result = ExecutionResult(ok=False, error=f"{type(exc).__name__}: {exc}")
        latency_ms = max(0.0, (time.time() - t0) * 1000.0)
        if result.backend is None:
            result.backend = backend_name
        if result.latency_ms is None:
            result.latency_ms = float(latency_ms)
        return _apply_failure_policy(result, hints=hints)

    def map(
        self,
        *,
        scope: str,
        task: str,
        items: Any,
        backend: Optional[str],
        call: Optional[Callable[..., Any]] = None,
        hints: Optional[Mapping[str, Any]] = None,
        context: Optional[Mapping[str, Any]] = None,
    ) -> ExecutionResult:
        payload: Dict[str, Any] = {"items": list(items)}
        if call is not None:
            payload["callable"] = call
        return self.run(
            scope=scope,
            task=task,
            payload=payload,
            backend=backend,
            hints=hints,
            context=context,
        )

    def submit(
        self,
        *,
        scope: str,
        task: str,
        payload: Optional[Mapping[str, Any]] = None,
        backend: Optional[str],
        hints: Optional[Mapping[str, Any]] = None,
        context: Optional[Mapping[str, Any]] = None,
    ) -> "AsyncHandle":
        self._require_backend(backend)
        backend_name = str(backend)
        merged: Dict[str, Any] = dict(payload or {})
        if context is not None:
            merged.setdefault("context", dict(context))
        if hints is not None:
            merged.setdefault("hints", dict(hints))

        runner = self.get(scope=str(scope), backend=backend_name)
        t0 = time.time()
        submit_fn = getattr(runner, "submit", None)
        try:
            if callable(submit_fn):
                raw = submit_fn(str(task), merged)
            else:
                raw = runner.run(str(task), merged)
        except Exception as exc:
            return _ImmediateHandle(
                ExecutionResult(ok=False, error=f"{type(exc).__name__}: {exc}", backend=backend_name)
            )
        return _wrap_async_result(raw, backend=backend_name, start_time=t0, hints=hints)

    def map_async(
        self,
        *,
        scope: str,
        task: str,
        items: Any,
        backend: Optional[str],
        call: Optional[Callable[..., Any]] = None,
        hints: Optional[Mapping[str, Any]] = None,
        context: Optional[Mapping[str, Any]] = None,
    ) -> "AsyncHandle":
        payload: Dict[str, Any] = {"items": list(items)}
        if call is not None:
            payload["callable"] = call
        return self.submit(
            scope=scope,
            task=task,
            payload=payload,
            backend=backend,
            hints=hints,
            context=context,
        )

    @staticmethod
    def _require_backend(backend: Optional[str]) -> None:
        if backend is None or str(backend).strip() == "":
            raise ValueError("backend must be provided explicitly (no implicit default)")


def _resolve_callable(payload: Mapping[str, Any]) -> Optional[Callable[..., Any]]:
    fn = payload.get("callable")
    if callable(fn):
        return fn
    ref = payload.get("task_ref")
    if isinstance(ref, str) and ":" in ref:
        mod, name = ref.split(":", 1)
        try:
            module = importlib.import_module(mod)
            target = getattr(module, name, None)
            if callable(target):
                return target
        except Exception:
            return None
    return None


def _coerce_result(raw: Any) -> ExecutionResult:
    if isinstance(raw, ExecutionResult):
        return raw
    if isinstance(raw, Mapping) and "ok" in raw:
        ok = bool(raw.get("ok"))
        error = raw.get("error")
        if error is not None and ok:
            ok = False
        return ExecutionResult(
            ok=ok,
            data=raw.get("data"),
            error=str(error) if error is not None else None,
            backend=raw.get("backend"),
            latency_ms=raw.get("latency_ms"),
            trace_id=raw.get("trace_id"),
            metrics=dict(raw.get("metrics") or {}),
        )
    return ExecutionResult(ok=True, data=raw)


def _apply_failure_policy(result: ExecutionResult, *, hints: Optional[Mapping[str, Any]]) -> ExecutionResult:
    policy = None
    if isinstance(hints, Mapping):
        policy = hints.get("failure_policy")
    policy_text = str(policy or "strict").strip().lower()
    if policy_text not in {"strict", "soft"}:
        policy_text = "strict"
    if result.ok:
        return result
    if policy_text == "strict":
        raise AccelerationError(result.error or "Acceleration task failed")
    return result


class AsyncHandle(Protocol):
    def done(self) -> bool:
        ...

    def result(self, timeout: Optional[float] = None) -> ExecutionResult:
        ...

    def cancel(self) -> bool:
        ...

    def status(self) -> str:
        ...


class _ImmediateHandle:
    def __init__(self, result: ExecutionResult) -> None:
        self._result = result

    def done(self) -> bool:
        return True

    def result(self, timeout: Optional[float] = None) -> ExecutionResult:
        return self._result

    def cancel(self) -> bool:
        return False

    def status(self) -> str:
        return "done" if self._result.ok else "failed"


class _FutureHandle:
    def __init__(
        self,
        future: Future,
        *,
        backend: str,
        start_time: float,
        hints: Optional[Mapping[str, Any]] = None,
    ) -> None:
        self._future = future
        self._backend = backend
        self._start_time = start_time
        self._hints = dict(hints or {})

    def done(self) -> bool:
        return self._future.done()

    def result(self, timeout: Optional[float] = None) -> ExecutionResult:
        try:
            raw = self._future.result(timeout=timeout)
            result = _coerce_result(raw)
        except FutureTimeoutError as exc:
            result = ExecutionResult(ok=False, error=f"TimeoutError: {exc}")
        except Exception as exc:
            result = ExecutionResult(ok=False, error=f"{type(exc).__name__}: {exc}")
        if result.backend is None:
            result.backend = self._backend
        if result.latency_ms is None:
            result.latency_ms = max(0.0, (time.time() - self._start_time) * 1000.0)
        return _apply_failure_policy(result, hints=self._hints)

    def cancel(self) -> bool:
        return bool(self._future.cancel())

    def status(self) -> str:
        if self._future.cancelled():
            return "cancelled"
        if self._future.done():
            try:
                if self._future.exception() is not None:
                    return "failed"
            except Exception:
                return "failed"
            return "done"
        return "running"


def _wrap_async_result(
    raw: Any,
    *,
    backend: str,
    start_time: float,
    hints: Optional[Mapping[str, Any]] = None,
) -> AsyncHandle:
    if isinstance(raw, Future):
        return _FutureHandle(raw, backend=backend, start_time=start_time, hints=hints)
    if isinstance(raw, ExecutionResult):
        return _ImmediateHandle(raw)
    if isinstance(raw, Mapping) and "ok" in raw:
        return _ImmediateHandle(_coerce_result(raw))
    return _ImmediateHandle(ExecutionResult(ok=True, data=raw, backend=backend))


def _call_task_ref(task_ref: str, args: tuple, kwargs: dict) -> Any:
    fn = _resolve_callable({"task_ref": task_ref})
    if not callable(fn):
        raise RuntimeError(f"task_ref '{task_ref}' is not callable")
    return fn(*args, **kwargs)


def _call_task_ref_map(task_ref: str, item: Any, args: tuple, kwargs: dict) -> Any:
    fn = _resolve_callable({"task_ref": task_ref})
    if not callable(fn):
        raise RuntimeError(f"task_ref '{task_ref}' is not callable")
    return fn(item, *args, **kwargs)


class ThreadPoolBackend:
    """Thread-based execution backend for generic L0 tasks."""

    def __init__(self, *, max_workers: Optional[int] = None) -> None:
        self.max_workers = max_workers

    def run(self, task: str, payload: Mapping[str, Any]) -> Any:
        return _run_pool_task(
            task=task,
            payload=payload,
            backend="thread",
            max_workers=self.max_workers,
        )

    def submit(self, task: str, payload: Mapping[str, Any]) -> Any:
        return _submit_pool_task(
            task=task,
            payload=payload,
            backend="thread",
            max_workers=self.max_workers,
        )


class ProcessPoolBackend:
    """Process-based execution backend for generic L0 tasks."""

    def __init__(self, *, max_workers: Optional[int] = None) -> None:
        self.max_workers = max_workers

    def run(self, task: str, payload: Mapping[str, Any]) -> Any:
        return _run_pool_task(
            task=task,
            payload=payload,
            backend="process",
            max_workers=self.max_workers,
        )

    def submit(self, task: str, payload: Mapping[str, Any]) -> Any:
        return _submit_pool_task(
            task=task,
            payload=payload,
            backend="process",
            max_workers=self.max_workers,
        )


class GpuBackend:
    """GPU execution backend (torch/cupy) with explicit task expectations.

    Notes:
    - This backend does not "magically" GPU-accelerate arbitrary callables.
    - The callable/task_ref must implement GPU logic and accept kwargs:
      backend="torch|cupy", device="cuda:0", unless overridden via payload.
    """

    def __init__(
        self,
        *,
        preferred_backend: str = "auto",
        device: str = "cuda:0",
        pass_backend_kwargs: bool = True,
    ) -> None:
        self.preferred_backend = str(preferred_backend or "auto")
        self.device = str(device or "cuda:0")
        self.pass_backend_kwargs = bool(pass_backend_kwargs)

    def run(self, task: str, payload: Mapping[str, Any]) -> Any:
        if not isinstance(payload, Mapping):
            return {"ok": False, "error": "payload must be a mapping", "metrics": {}}

        backend = _select_gpu_backend(self.preferred_backend)
        if backend is None:
            return {"ok": False, "error": "no gpu backend available", "metrics": {}}

        task_name = str(task or "").strip().lower()
        fn = _resolve_callable(payload)
        if not callable(fn):
            return {"ok": False, "error": "callable or task_ref required", "metrics": {}}

        args = payload.get("args", ())
        kwargs = dict(payload.get("kwargs", {}) or {})
        if self.pass_backend_kwargs:
            kwargs.setdefault("backend", backend)
            kwargs.setdefault("device", self.device)

        if task_name in {"map", "batch"}:
            items = payload.get("items", None)
            if items is None:
                return {"ok": False, "error": "map task requires payload['items']", "metrics": {}}
            try:
                out = [fn(item, *args, **kwargs) for item in list(items)]
                return {"ok": True, "data": out, "metrics": {"backend": backend}}
            except Exception as exc:
                return {"ok": False, "error": f"{type(exc).__name__}: {exc}", "metrics": {"backend": backend}}

        try:
            out = fn(*args, **kwargs)
            return {"ok": True, "data": out, "metrics": {"backend": backend}}
        except Exception as exc:
            return {"ok": False, "error": f"{type(exc).__name__}: {exc}", "metrics": {"backend": backend}}

    def submit(self, task: str, payload: Mapping[str, Any]) -> Any:
        return _submit_via_thread(self.run, task, payload)


def _select_gpu_backend(preferred: str) -> Optional[str]:
    pref = str(preferred or "auto").strip().lower()
    candidates = [pref] if pref in {"torch", "cupy"} else ["torch", "cupy"]
    for name in candidates:
        try:
            if name == "torch":
                import torch  # type: ignore

                if bool(torch.cuda.is_available()):
                    return "torch"
            if name == "cupy":
                import cupy  # type: ignore  # noqa: F401

                return "cupy"
        except Exception:
            continue
    return None


def _run_pool_task(
    *,
    task: str,
    payload: Mapping[str, Any],
    backend: str,
    max_workers: Optional[int],
) -> Mapping[str, Any]:
    if not isinstance(payload, Mapping):
        return {"ok": False, "error": "payload must be a mapping", "metrics": {}}

    task_name = str(task or "").strip().lower()
    hints = payload.get("hints") if isinstance(payload.get("hints"), Mapping) else {}
    timeout_ms = hints.get("timeout_ms") if isinstance(hints, Mapping) else None
    retries = hints.get("retries") if isinstance(hints, Mapping) else None
    timeout_s = None if timeout_ms is None else max(0.0, float(timeout_ms) / 1000.0)
    retry_count = max(0, int(retries or 0))

    if task_name in {"map", "batch"}:
        return _run_pool_map(
            payload=payload,
            backend=backend,
            max_workers=max_workers,
            timeout_s=timeout_s,
            retry_count=retry_count,
        )
    return _run_pool_call(
        payload=payload,
        backend=backend,
        max_workers=max_workers,
        timeout_s=timeout_s,
        retry_count=retry_count,
    )


def _submit_pool_task(
    *,
    task: str,
    payload: Mapping[str, Any],
    backend: str,
    max_workers: Optional[int],
) -> Any:
    if not isinstance(payload, Mapping):
        return {"ok": False, "error": "payload must be a mapping", "metrics": {}}

    def _runner() -> Any:
        return _run_pool_task(
            task=task,
            payload=payload,
            backend=backend,
            max_workers=max_workers,
        )

    launcher = ThreadPoolExecutor(max_workers=1)
    fut = launcher.submit(_runner)

    def _cleanup(_fut: Future) -> None:
        try:
            launcher.shutdown(wait=False)
        except Exception:
            return

    fut.add_done_callback(_cleanup)
    return fut


def _submit_via_thread(fn: Callable[..., Any], *args: Any, **kwargs: Any) -> Future:
    executor = ThreadPoolExecutor(max_workers=1)
    fut = executor.submit(fn, *args, **kwargs)

    def _cleanup(_fut: Future) -> None:
        try:
            executor.shutdown(wait=False)
        except Exception:
            return

    fut.add_done_callback(_cleanup)
    return fut


def _run_pool_call(
    *,
    payload: Mapping[str, Any],
    backend: str,
    max_workers: Optional[int],
    timeout_s: Optional[float],
    retry_count: int,
) -> Mapping[str, Any]:
    fn = _resolve_callable(payload)
    task_ref = payload.get("task_ref")
    args = payload.get("args", ())
    kwargs = payload.get("kwargs", {})

    if backend == "process" and fn is not None and task_ref is None:
        try:
            pickle.dumps(fn)
        except Exception:
            return {
                "ok": False,
                "error": "process backend requires picklable callable or task_ref",
                "metrics": {"retry_count": 0},
            }

    def _invoke() -> Any:
        if backend == "process" and isinstance(task_ref, str):
            return _call_task_ref(task_ref, tuple(args), dict(kwargs))
        if not callable(fn):
            raise RuntimeError("callable or task_ref required")
        return fn(*args, **kwargs)

    exec_cls = ProcessPoolExecutor if backend == "process" else ThreadPoolExecutor
    attempts = max(1, retry_count + 1)
    last_exc: Optional[Exception] = None
    for _ in range(attempts):
        with exec_cls(max_workers=max_workers) as ex:
            fut = ex.submit(_invoke)
            try:
                return {"ok": True, "data": fut.result(timeout=timeout_s), "metrics": {"retry_count": retry_count}}
            except FutureTimeoutError as exc:
                last_exc = exc
            except Exception as exc:
                last_exc = exc

    err = f"{type(last_exc).__name__}: {last_exc}" if last_exc is not None else "unknown error"
    return {"ok": False, "error": err, "metrics": {"retry_count": retry_count}}


def _run_pool_map(
    *,
    payload: Mapping[str, Any],
    backend: str,
    max_workers: Optional[int],
    timeout_s: Optional[float],
    retry_count: int,
) -> Mapping[str, Any]:
    items = payload.get("items", None)
    if items is None:
        return {"ok": False, "error": "map task requires payload['items']", "metrics": {}}
    items_list = list(items)

    fn = _resolve_callable(payload)
    task_ref = payload.get("task_ref")
    args = payload.get("args", ())
    kwargs = payload.get("kwargs", {})

    if backend == "process" and fn is not None and task_ref is None:
        try:
            pickle.dumps(fn)
        except Exception:
            return {
                "ok": False,
                "error": "process backend requires picklable callable or task_ref",
                "metrics": {"retry_count": 0},
            }

    def _invoke(item: Any) -> Any:
        if backend == "process" and isinstance(task_ref, str):
            return _call_task_ref_map(task_ref, item, tuple(args), dict(kwargs))
        if not callable(fn):
            raise RuntimeError("callable or task_ref required")
        return fn(item, *args, **kwargs)

    exec_cls = ProcessPoolExecutor if backend == "process" else ThreadPoolExecutor
    results: list[Any] = [None] * len(items_list)
    errors: list[dict] = []

    with exec_cls(max_workers=max_workers) as ex:
        futures = {ex.submit(_invoke, item): idx for idx, item in enumerate(items_list)}
        for fut, idx in futures.items():
            try:
                results[idx] = fut.result(timeout=timeout_s)
            except FutureTimeoutError as exc:
                errors.append({"index": int(idx), "error": f"TimeoutError: {exc}"})
            except Exception as exc:
                errors.append({"index": int(idx), "error": f"{type(exc).__name__}: {exc}"})

    if errors and retry_count > 0:
        for attempt in range(retry_count):
            if not errors:
                break
            remaining = list(errors)
            errors = []
            for rec in remaining:
                idx = rec["index"]
                try:
                    results[idx] = _invoke(items_list[idx])
                except Exception as exc:
                    errors.append({"index": int(idx), "error": f"{type(exc).__name__}: {exc}"})

    metrics = {"error_count": len(errors), "retry_count": retry_count}
    if errors:
        return {"ok": False, "data": results, "error": "map task failed", "metrics": metrics, "errors": errors}
    return {"ok": True, "data": results, "metrics": metrics}
