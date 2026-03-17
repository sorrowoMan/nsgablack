"""Context projection helpers used by SolverBase."""

from __future__ import annotations

from typing import Any, Callable, Dict, Optional

import numpy as np

from ...core.state.context_keys import (
    KEY_BEST_OBJECTIVE,
    KEY_BEST_X,
    KEY_SNAPSHOT_KEY,
)


def _report_debug_soft_error(
    *,
    solver: Any,
    report_soft_error_fn: Callable[..., Any],
    logger: Any,
    event: str,
    exc: Exception,
) -> None:
    report_soft_error_fn(
        component="SolverBase",
        event=event,
        exc=exc,
        logger=logger,
        context_store=getattr(solver, "context_store", None),
        strict=False,
        level="debug",
    )


def build_solver_context(
    solver: Any,
    *,
    individual_id: Optional[int] = None,
    constraints: Optional[np.ndarray] = None,
    violation: Optional[float] = None,
    individual: Optional[np.ndarray] = None,
    report_soft_error_fn: Callable[..., Any],
    logger: Any,
) -> Dict[str, Any]:
    ctx = {
        "problem": solver.problem,
        "generation": solver.generation,
        "constraints": (constraints.tolist() if constraints is not None else []),
        "constraint_violation": float(violation or 0.0),
        "individual_id": individual_id,
    }

    try:
        persisted = solver.context_store.snapshot()
        if persisted:
            merged = dict(persisted)
            merged.update(ctx)
            ctx = merged
    except Exception as exc:
        _report_debug_soft_error(
            solver=solver,
            report_soft_error_fn=report_soft_error_fn,
            logger=logger,
            event="context_store_snapshot",
            exc=exc,
        )

    solver._strip_large_context(ctx)
    best_x, best_obj = solver._get_best_snapshot()
    ctx[KEY_BEST_X] = best_x
    ctx[KEY_BEST_OBJECTIVE] = best_obj
    if individual is not None:
        ctx["individual"] = individual

    dynamic = getattr(solver, "dynamic_signals", None)
    if dynamic is not None:
        ctx["dynamic"] = dynamic
    phase_id = getattr(solver, "dynamic_phase_id", None)
    if phase_id is not None:
        ctx["phase_id"] = phase_id

    plugin_manager = getattr(solver, "plugin_manager", None)
    if plugin_manager is not None:
        try:
            ctx = plugin_manager.dispatch("on_context_build", ctx) or ctx
        except Exception as exc:
            report_soft_error_fn(
                component="SolverBase",
                event="plugin_dispatch_on_context_build",
                exc=exc,
                logger=logger,
                context_store=getattr(solver, "context_store", None),
                strict=bool(getattr(plugin_manager, "strict", False)),
            )

    solver._strip_large_context(ctx)
    solver._attach_snapshot_refs(ctx, allow_write=True)
    try:
        solver.context_store.update(ctx, ttl_seconds=solver.context_store_ttl_seconds)
    except Exception as exc:
        _report_debug_soft_error(
            solver=solver,
            report_soft_error_fn=report_soft_error_fn,
            logger=logger,
            event="context_store_update_build_context",
            exc=exc,
        )
    solver._purge_large_context_store()
    return ctx


def get_solver_context_view(
    solver: Any,
    *,
    report_soft_error_fn: Callable[..., Any],
    logger: Any,
) -> Dict[str, Any]:
    ctx = solver.build_context()
    ctx["evaluation_count"] = int(getattr(solver, "evaluation_count", 0))

    for key, value in solver._collect_runtime_context_projection().items():
        if value is None:
            continue
        ctx[key] = value

    best_x, best_obj = solver._get_best_snapshot()
    ctx[KEY_BEST_X] = best_x
    ctx[KEY_BEST_OBJECTIVE] = best_obj
    solver._strip_large_context(ctx)
    solver._attach_snapshot_refs(ctx, allow_write=True)
    if bool(getattr(solver, "snapshot_strict", False)):
        ensure_snapshot_readable(solver, ctx)
    try:
        solver.context_store.update(ctx, ttl_seconds=solver.context_store_ttl_seconds)
    except Exception as exc:
        _report_debug_soft_error(
            solver=solver,
            report_soft_error_fn=report_soft_error_fn,
            logger=logger,
            event="context_store_update_get_context",
            exc=exc,
        )
    solver._purge_large_context_store()
    return ctx


def ensure_snapshot_readable(solver: Any, ctx: Dict[str, Any]) -> None:
    key = ctx.get(KEY_SNAPSHOT_KEY)
    if key is None or str(key).strip() == "":
        has_state = any(
            getattr(solver, attr, None) is not None
            for attr in ("population", "objectives", "constraint_violations")
        )
        if has_state:
            raise RuntimeError("snapshot_key missing while solver has population/objectives/violations")
        return
    payload = solver.read_snapshot(str(key))
    if payload is None:
        raise RuntimeError("snapshot_key present but snapshot_store returned None")
