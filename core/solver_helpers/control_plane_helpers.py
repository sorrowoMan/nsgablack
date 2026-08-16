"""Control-plane helper utilities for SolverBase."""

from __future__ import annotations

from typing import Any, Dict, Mapping, Optional

from ..state.context_keys import (
    KEY_BEST_OBJECTIVE,
    KEY_BEST_X,
    KEY_EVALUATION_COUNT,
    KEY_GENERATION,
    KEY_PARETO_OBJECTIVES,
    KEY_PARETO_SOLUTIONS,
)


def _store_set(store: Any, key: str, value: Any) -> None:
    if store is None:
        return
    set_fn = getattr(store, "set", None)
    if callable(set_fn):
        try:
            set_fn(key, value)
        except Exception:
            return
    elif isinstance(store, dict):
        store[key] = value


def collect_runtime_context_projection(
    solver: Any,
    *,
    report_soft_error_fn: Any = None,
    logger: Any = None,
    keys: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    """Collect a small runtime projection from solver and adapter state."""
    if isinstance(solver, Mapping):
        key_map = dict(keys or {})
        return {dst: solver.get(src) for src, dst in key_map.items() if src in solver}

    out: Dict[str, Any] = {
        KEY_GENERATION: int(getattr(solver, "generation", 0) or 0),
        KEY_EVALUATION_COUNT: int(getattr(solver, "evaluation_count", 0) or 0),
        KEY_BEST_X: getattr(solver, "best_x", None),
        KEY_BEST_OBJECTIVE: getattr(solver, "best_objective", getattr(solver, "best_f", None)),
    }
    adapter = getattr(solver, "adapter", None)
    projector = getattr(adapter, "get_runtime_context_projection", None)
    if callable(projector):
        try:
            extra = projector()
        except TypeError:
            extra = projector(solver)
        except Exception as exc:
            if callable(report_soft_error_fn):
                report_soft_error_fn(
                    component="SolverBase",
                    event="adapter_runtime_context_projection",
                    exc=exc,
                    logger=logger,
                    context_store=getattr(solver, "context_store", None),
                    strict=False,
                    level="debug",
                )
            extra = None
        if isinstance(extra, Mapping):
            out.update(dict(extra))
    return out


def increment_evaluation_counter(
    solver: Any,
    delta: int = 1,
    *,
    report_soft_error_fn: Any = None,
    logger: Any = None,
) -> int:
    """Increment solver.evaluation_count and mirror it to context_store."""
    if isinstance(solver, Mapping):
        return int(solver.get(KEY_EVALUATION_COUNT, solver.get("evaluation_count", 0)) or 0) + int(delta)
    current = int(getattr(solver, "evaluation_count", 0) or 0)
    value = current + int(delta)
    setattr(solver, "evaluation_count", value)
    _store_set(getattr(solver, "context_store", None), KEY_EVALUATION_COUNT, value)
    return value


def get_best_snapshot_fields(
    solver: Any,
    *,
    report_soft_error_fn: Any = None,
    logger: Any = None,
) -> tuple[Any, Any]:
    """Return `(best_x, best_objective)` from solver/context store."""
    if isinstance(solver, Mapping):
        return solver.get(KEY_BEST_X), solver.get(KEY_BEST_OBJECTIVE)
    best_x = getattr(solver, "best_x", None)
    best_obj = getattr(solver, "best_objective", None)
    if best_obj is None:
        best_obj = getattr(solver, "best_f", None)
    store = getattr(solver, "context_store", None)
    get_fn = getattr(store, "get", None)
    if callable(get_fn):
        if best_x is None:
            best_x = get_fn(KEY_BEST_X, None)
        if best_obj is None:
            best_obj = get_fn(KEY_BEST_OBJECTIVE, None)
    return best_x, best_obj


def set_best_snapshot_fields(
    solver: Any,
    best_x: Any = None,
    best_objective: Any = None,
    *,
    report_soft_error_fn: Any = None,
    logger: Any = None,
) -> None:
    """Set best solution fields on solver and context_store."""
    if isinstance(solver, dict):
        solver[KEY_BEST_X] = best_x
        solver[KEY_BEST_OBJECTIVE] = best_objective
        return
    setattr(solver, "best_x", best_x)
    setattr(solver, "best_objective", best_objective)
    try:
        setattr(solver, "best_f", None if best_objective is None else float(best_objective))
    except Exception:
        pass
    store = getattr(solver, "context_store", None)
    _store_set(store, KEY_BEST_X, best_x)
    _store_set(store, KEY_BEST_OBJECTIVE, best_objective)


def set_generation_value(solver: Any, generation: int) -> int:
    """Set generation on solver and context_store."""
    value = int(generation)
    if isinstance(solver, dict):
        solver[KEY_GENERATION] = value
        return value
    setattr(solver, "generation", value)
    _store_set(getattr(solver, "context_store", None), KEY_GENERATION, value)
    return value


def set_pareto_snapshot_fields(
    solver: Any,
    solutions: Any = None,
    objectives: Any = None,
    *,
    report_soft_error_fn: Any = None,
    logger: Any = None,
) -> None:
    """Set Pareto fields on solver and context_store."""
    if isinstance(solver, dict):
        solver[KEY_PARETO_SOLUTIONS] = solutions
        solver[KEY_PARETO_OBJECTIVES] = objectives
        return
    setattr(solver, "pareto_solutions", solutions)
    setattr(solver, "pareto_objectives", objectives)
    store = getattr(solver, "context_store", None)
    _store_set(store, KEY_PARETO_SOLUTIONS, solutions)
    _store_set(store, KEY_PARETO_OBJECTIVES, objectives)


__all__ = [
    "collect_runtime_context_projection",
    "increment_evaluation_counter",
    "get_best_snapshot_fields",
    "set_best_snapshot_fields",
    "set_generation_value",
    "set_pareto_snapshot_fields",
]
