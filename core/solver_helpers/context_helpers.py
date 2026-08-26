"""Context helper utilities for SolverBase."""

from __future__ import annotations

from typing import Any, Dict, Mapping, Optional

from blackbase.context.context_keys import (
    KEY_BEST_CANDIDATE_REF,
    KEY_BEST_OBJECTIVE,
    KEY_BEST_X,
    KEY_BOUNDS,
    KEY_CONSTRAINT_VIOLATION,
    KEY_CONSTRAINTS,
    KEY_EVALUATION_COUNT,
    KEY_GENERATION,
    KEY_INDIVIDUAL,
    KEY_INDIVIDUAL_ID,
    KEY_OBJECTIVES,
    KEY_OBJECTIVES_REF,
    KEY_PARETO_OBJECTIVES,
    KEY_PARETO_OBJECTIVES_REF,
    KEY_PARETO_SOLUTIONS,
    KEY_PARETO_SOLUTIONS_REF,
    KEY_POPULATION,
    KEY_POPULATION_REF,
    KEY_PROBLEM,
    KEY_RESOURCE_CONTEXT,
    KEY_RESOURCE_CONTEXT_SHORT,
    KEY_SNAPSHOT_KEY,
)


# The authoritative incumbent publisher is the only writer for these keys.
# ``build_solver_context`` may project them into its returned local view, but
# must never replay a captured value into the shared ContextStore.
_INCUMBENT_CONTEXT_STORE_OWNED_KEYS = frozenset(
    (
        KEY_BEST_X,
        KEY_BEST_CANDIDATE_REF,
        KEY_BEST_OBJECTIVE,
    )
)


def _store_snapshot(store: Any) -> Dict[str, Any]:
    if store is None:
        return {}
    snap = getattr(store, "snapshot", None)
    if callable(snap):
        return dict(snap())
    if isinstance(store, Mapping):
        return dict(store)
    return {}


def _set_store_values(store: Any, values: Mapping[str, Any]) -> None:
    if store is None:
        return
    update = getattr(store, "update", None)
    if callable(update):
        update(dict(values))
        return
    set_fn = getattr(store, "set", None)
    if callable(set_fn):
        for key, value in values.items():
            set_fn(str(key), value)


def build_solver_context(
    solver: Any,
    *,
    individual_id: Optional[int] = None,
    constraints: Optional[Any] = None,
    violation: Optional[float] = None,
    individual: Optional[Any] = None,
    report_soft_error_fn: Any = None,
    logger: Any = None,
    allow_snapshot_write: bool = True,
) -> Dict[str, Any]:
    """Build a lightweight runtime context from a solver instance."""
    purge_large = getattr(solver, "_purge_large_context_store", None)
    if callable(purge_large):
        purge_large()
    ctx = _store_snapshot(getattr(solver, "context_store", None))
    strip_large = getattr(solver, "_strip_large_context", None)
    if callable(strip_large):
        strip_large(ctx)
    problem = getattr(solver, "problem", None)
    ctx.update(
        {
            KEY_PROBLEM: getattr(problem, "name", None),
            KEY_BOUNDS: getattr(solver, "var_bounds", getattr(problem, "bounds", None)),
            KEY_GENERATION: int(getattr(solver, "generation", 0) or 0),
            KEY_EVALUATION_COUNT: int(getattr(solver, "evaluation_count", 0) or 0),
        }
    )
    resource = getattr(solver, "resource_context", None)
    if resource is not None:
        as_dict = getattr(resource, "as_dict", None)
        payload = dict(as_dict()) if callable(as_dict) else dict(resource)
        context_items = getattr(resource, "context_items", None)
        if callable(context_items):
            ctx.update(dict(context_items(prefix="resource")))
        ctx[KEY_RESOURCE_CONTEXT] = payload
        ctx[KEY_RESOURCE_CONTEXT_SHORT] = payload
    if individual_id is not None:
        ctx[KEY_INDIVIDUAL_ID] = int(individual_id)
    if constraints is not None:
        ctx[KEY_CONSTRAINTS] = constraints
    if violation is not None:
        ctx[KEY_CONSTRAINT_VIOLATION] = float(violation)
    if individual is not None:
        ctx[KEY_INDIVIDUAL] = individual

    attach = getattr(solver, "_attach_snapshot_refs", None)
    if callable(attach):
        try:
            attach(ctx, allow_write=bool(allow_snapshot_write))
        except Exception as exc:
            if callable(report_soft_error_fn):
                report_soft_error_fn(
                    component="SolverBase",
                    event="context_attach_snapshot_refs",
                    exc=exc,
                    logger=logger,
                    context_store=getattr(solver, "context_store", None),
                    strict=False,
                    level="debug",
                )

    governance = getattr(solver, "_apply_runtime_governance_context", None)
    if callable(governance):
        try:
            ctx = governance(ctx) or ctx
        except Exception as exc:
            if callable(report_soft_error_fn):
                report_soft_error_fn(
                    component="SolverBase",
                    event="context_runtime_governance",
                    exc=exc,
                    logger=logger,
                    context_store=getattr(solver, "context_store", None),
                    strict=bool(getattr(solver, "plugin_strict", False)),
                )

    plugin_manager = getattr(solver, "plugin_manager", None)
    hook = getattr(plugin_manager, "on_context_build", None)
    if callable(hook):
        try:
            out = hook(ctx)
            if isinstance(out, dict):
                ctx = out
        except Exception as exc:
            if bool(getattr(solver, "plugin_strict", False)):
                raise
            if callable(report_soft_error_fn):
                report_soft_error_fn(
                    component="SolverBase",
                    event="context_plugin_build",
                    exc=exc,
                    logger=logger,
                    context_store=getattr(solver, "context_store", None),
                    strict=False,
                )

    if callable(strip_large):
        strip_large(ctx)
    project_incumbent = getattr(solver, "project_incumbent_context", None)
    if callable(project_incumbent):
        project_incumbent(ctx)
    if bool(getattr(solver, "context_store_update_on_build", False)):
        writeback = {
            key: value
            for key, value in ctx.items()
            if key not in _INCUMBENT_CONTEXT_STORE_OWNED_KEYS
        }
        _set_store_values(getattr(solver, "context_store", None), writeback)
    if callable(purge_large):
        purge_large()
    return ctx


def ensure_snapshot_readable(solver: Any, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Hydrate known snapshot refs into a context when a readable snapshot exists."""
    if context is None and isinstance(solver, Mapping):
        return dict(solver)
    ctx = dict(context or {})
    reader = getattr(solver, "read_snapshot", None)
    if not callable(reader):
        return ctx
    primary_key = (
        ctx.get(KEY_SNAPSHOT_KEY)
        or ctx.get(KEY_POPULATION_REF)
        or ctx.get(KEY_OBJECTIVES_REF)
    )
    best_key = ctx.get(KEY_BEST_CANDIDATE_REF)
    snapshot_keys: list[str] = []
    for key in (primary_key, best_key):
        if key and str(key) not in snapshot_keys:
            snapshot_keys.append(str(key))
    if not snapshot_keys:
        return ctx
    for snapshot_key in snapshot_keys:
        try:
            payload = reader(snapshot_key)
        except Exception:
            continue
        if not isinstance(payload, Mapping):
            continue
        for key_name in (
            KEY_BEST_X,
            KEY_POPULATION,
            KEY_OBJECTIVES,
            KEY_PARETO_SOLUTIONS,
            KEY_PARETO_OBJECTIVES,
        ):
            if key_name not in ctx and key_name in payload:
                ctx[key_name] = payload[key_name]
    return ctx


def get_solver_context_view(
    solver: Any,
    *,
    report_soft_error_fn: Any = None,
    logger: Any = None,
    keys: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    """Return a current runtime context view for monitoring/reporting."""
    if isinstance(solver, Mapping):
        src = dict(solver)
        key_map = dict(keys or {})
        return {dst: src.get(src_key) for src_key, dst in key_map.items()} if key_map else src

    ctx = build_solver_context(
        solver,
        report_soft_error_fn=report_soft_error_fn,
        logger=logger,
        allow_snapshot_write=True,
    )
    runtime_projection = getattr(solver, "_collect_runtime_context_projection", None)
    if callable(runtime_projection):
        try:
            for key, value in dict(runtime_projection() or {}).items():
                if value is not None:
                    ctx[str(key)] = value
        except Exception as exc:
            if callable(report_soft_error_fn):
                report_soft_error_fn(
                    component="SolverBase",
                    event="context_runtime_projection",
                    exc=exc,
                    logger=logger,
                    context_store=getattr(solver, "context_store", None),
                    strict=False,
                    level="debug",
                )
    project_incumbent = getattr(solver, "project_incumbent_context", None)
    get_incumbent = getattr(solver, "get_incumbent", None)
    incumbent = get_incumbent() if callable(get_incumbent) else None
    if callable(project_incumbent):
        project_incumbent(ctx)
    elif incumbent is None:
        if getattr(solver, "best_x", None) is not None:
            ctx[KEY_BEST_X] = getattr(solver, "best_x", None)
        if getattr(solver, "best_objective", None) is not None:
            ctx[KEY_BEST_OBJECTIVE] = getattr(solver, "best_objective", None)
        elif getattr(solver, "best_f", None) is not None:
            ctx[KEY_BEST_OBJECTIVE] = getattr(solver, "best_f", None)

    if getattr(solver, "pareto_solutions", None) is not None:
        ctx.setdefault(KEY_PARETO_SOLUTIONS_REF, ctx.get(KEY_SNAPSHOT_KEY))
    if getattr(solver, "pareto_objectives", None) is not None:
        ctx.setdefault(KEY_PARETO_OBJECTIVES_REF, ctx.get(KEY_SNAPSHOT_KEY))
    return ctx


__all__ = [
    "build_solver_context",
    "ensure_snapshot_readable",
    "get_solver_context_view",
]
