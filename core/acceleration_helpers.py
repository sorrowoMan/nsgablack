"""Unified helpers for optional L0 acceleration usage."""

from __future__ import annotations

from typing import Any, Callable, Iterable, Mapping, Optional

from .acceleration import ExecutionResult


def maybe_accel_run(
    *,
    solver: Any,
    scope: str,
    task: str,
    payload: Mapping[str, Any],
    backend: Optional[str],
    hints: Optional[Mapping[str, Any]] = None,
    context: Optional[Mapping[str, Any]] = None,
) -> ExecutionResult:
    """Run a task via L0 if backend is provided; otherwise run inline."""
    if backend is None:
        callable_fn = payload.get("callable")
        if not callable(callable_fn):
            return ExecutionResult(ok=False, error="missing callable for inline execution")
        try:
            data = callable_fn(*payload.get("args", ()), **payload.get("kwargs", {}))
            return ExecutionResult(ok=True, data=data)
        except Exception as exc:
            return ExecutionResult(ok=False, error=f"{type(exc).__name__}: {exc}")

    accel = getattr(solver, "accel", None)
    if accel is None:
        return ExecutionResult(ok=False, error="solver.accel missing")
    return accel.run(
        scope=scope,
        task=task,
        payload=payload,
        backend=backend,
        hints=hints,
        context=context,
    )


def maybe_accel_map(
    *,
    solver: Any,
    scope: str,
    task: str,
    items: Iterable[Any],
    call: Callable[..., Any],
    backend: Optional[str],
    hints: Optional[Mapping[str, Any]] = None,
    context: Optional[Mapping[str, Any]] = None,
) -> ExecutionResult:
    """Map via L0 if backend is provided; otherwise run inline."""
    if backend is None:
        try:
            data = [call(item) for item in list(items)]
            return ExecutionResult(ok=True, data=data)
        except Exception as exc:
            return ExecutionResult(ok=False, error=f"{type(exc).__name__}: {exc}")

    accel = getattr(solver, "accel", None)
    if accel is None:
        return ExecutionResult(ok=False, error="solver.accel missing")
    return accel.map(
        scope=scope,
        task=task,
        items=items,
        call=call,
        backend=backend,
        hints=hints,
        context=context,
    )
