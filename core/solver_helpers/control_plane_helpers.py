"""Control-plane helper functions used by SolverBase."""

from __future__ import annotations

from typing import Any, Callable, Dict, Optional, Tuple

import numpy as np


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


def set_generation_value(solver: Any, generation: int) -> int:
    value = int(generation)
    setattr(solver, "generation", value)
    return value


def increment_evaluation_counter(
    solver: Any,
    delta: int,
    *,
    report_soft_error_fn: Callable[..., Any],
    logger: Any,
) -> int:
    try:
        step = int(delta)
    except Exception as exc:
        _report_debug_soft_error(
            solver=solver,
            report_soft_error_fn=report_soft_error_fn,
            logger=logger,
            event="increment_evaluation_count_cast",
            exc=exc,
        )
        step = 0
    current = int(getattr(solver, "evaluation_count", 0) or 0) + step
    setattr(solver, "evaluation_count", current)
    return current


def set_best_snapshot_fields(
    solver: Any,
    best_x: Any,
    best_objective: Any,
    *,
    report_soft_error_fn: Callable[..., Any],
    logger: Any,
) -> None:
    setattr(solver, "best_x", best_x)
    try:
        setattr(solver, "best_objective", None if best_objective is None else float(best_objective))
    except Exception as exc:
        _report_debug_soft_error(
            solver=solver,
            report_soft_error_fn=report_soft_error_fn,
            logger=logger,
            event="set_best_snapshot_cast",
            exc=exc,
        )
        setattr(solver, "best_objective", best_objective)


def set_pareto_snapshot_fields(
    solver: Any,
    solutions: Any,
    objectives: Any,
    *,
    report_soft_error_fn: Callable[..., Any],
    logger: Any,
) -> None:
    try:
        setattr(solver, "pareto_solutions", None if solutions is None else np.asarray(solutions))
    except Exception as exc:
        _report_debug_soft_error(
            solver=solver,
            report_soft_error_fn=report_soft_error_fn,
            logger=logger,
            event="set_pareto_snapshot_solutions_cast",
            exc=exc,
        )
        setattr(solver, "pareto_solutions", solutions)

    try:
        setattr(solver, "pareto_objectives", None if objectives is None else np.asarray(objectives))
    except Exception as exc:
        _report_debug_soft_error(
            solver=solver,
            report_soft_error_fn=report_soft_error_fn,
            logger=logger,
            event="set_pareto_snapshot_objectives_cast",
            exc=exc,
        )
        setattr(solver, "pareto_objectives", objectives)


def get_best_snapshot_fields(
    solver: Any,
    *,
    report_soft_error_fn: Callable[..., Any],
    logger: Any,
) -> Tuple[Optional[Any], Optional[float]]:
    best_x = getattr(solver, "best_x", None)
    best_obj = getattr(solver, "best_objective", None)

    if best_obj is None:
        best_f = getattr(solver, "best_f", None)
        if best_f is not None:
            try:
                best_obj = float(best_f)
            except Exception:
                best_obj = None

    objectives = getattr(solver, "objectives", None)
    if best_obj is None and objectives is not None:
        try:
            obj = np.asarray(objectives, dtype=float)
            if obj.size > 0:
                if obj.ndim == 1:
                    best_obj = float(np.min(obj))
                else:
                    scores = np.sum(obj, axis=1)
                    violations = getattr(solver, "constraint_violations", None)
                    if violations is not None:
                        vio = np.asarray(violations, dtype=float).reshape(-1)
                        if vio.shape[0] == scores.shape[0]:
                            scores = scores + vio * 1e6
                    best_idx = int(np.argmin(scores))
                    best_obj = float(scores[best_idx])
                    if best_x is None:
                        population = getattr(solver, "population", None)
                        if population is not None:
                            pop = np.asarray(population)
                            if pop.ndim >= 2 and best_idx < pop.shape[0]:
                                best_x = pop[best_idx]
        except Exception as exc:
            _report_debug_soft_error(
                solver=solver,
                report_soft_error_fn=report_soft_error_fn,
                logger=logger,
                event="get_best_snapshot",
                exc=exc,
            )

    return best_x, best_obj


def collect_runtime_context_projection(
    solver: Any,
    *,
    report_soft_error_fn: Callable[..., Any],
    logger: Any,
) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    projection_writers: Dict[str, str] = {}

    adapter = getattr(solver, "adapter", None)
    if adapter is None:
        setattr(solver, "_runtime_projection_writers", projection_writers)
        return out

    projector = getattr(adapter, "get_runtime_context_projection", None)
    source_getter = getattr(adapter, "get_runtime_context_projection_sources", None)
    if not callable(projector):
        setattr(solver, "_runtime_projection_writers", projection_writers)
        return out

    try:
        proj = projector(solver)
    except Exception as exc:
        _report_debug_soft_error(
            solver=solver,
            report_soft_error_fn=report_soft_error_fn,
            logger=logger,
            event="adapter_runtime_projection",
            exc=exc,
        )
        proj = None

    try:
        proj_sources = source_getter(solver) if callable(source_getter) else {}
    except Exception as exc:
        _report_debug_soft_error(
            solver=solver,
            report_soft_error_fn=report_soft_error_fn,
            logger=logger,
            event="adapter_runtime_projection_sources",
            exc=exc,
        )
        proj_sources = {}

    if not isinstance(proj_sources, dict):
        proj_sources = {}
    if isinstance(proj, dict):
        for key, value in proj.items():
            if key is None or value is None:
                continue
            key_str = str(key)
            out[key_str] = value
            source = proj_sources.get(key_str)
            if source:
                projection_writers[key_str] = str(source)
            else:
                projection_writers[key_str] = f"adapter.{adapter.__class__.__name__}"

    setattr(solver, "_runtime_projection_writers", projection_writers)
    return out
