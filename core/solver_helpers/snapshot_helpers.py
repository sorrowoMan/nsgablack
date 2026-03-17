"""Snapshot/context helper functions used by SolverBase."""

from __future__ import annotations

from typing import Any, Dict, Optional

import numpy as np

from ...core.state.context_keys import (
    KEY_CONSTRAINT_VIOLATIONS,
    KEY_CONSTRAINT_VIOLATIONS_REF,
    KEY_DECISION_TRACE,
    KEY_DECISION_TRACE_REF,
    KEY_HISTORY,
    KEY_HISTORY_REF,
    KEY_OBJECTIVES,
    KEY_OBJECTIVES_REF,
    KEY_PARETO_OBJECTIVES,
    KEY_PARETO_OBJECTIVES_REF,
    KEY_PARETO_SOLUTIONS,
    KEY_PARETO_SOLUTIONS_REF,
    KEY_POPULATION,
    KEY_POPULATION_REF,
    KEY_SNAPSHOT_BACKEND,
    KEY_SNAPSHOT_KEY,
    KEY_SNAPSHOT_META,
    KEY_SNAPSHOT_SCHEMA,
)


LARGE_CONTEXT_KEYS = (
    KEY_POPULATION,
    KEY_OBJECTIVES,
    KEY_CONSTRAINT_VIOLATIONS,
    KEY_PARETO_SOLUTIONS,
    KEY_PARETO_OBJECTIVES,
    KEY_HISTORY,
    KEY_DECISION_TRACE,
)


def strip_large_context_fields(ctx: Dict[str, Any]) -> None:
    for key in LARGE_CONTEXT_KEYS:
        if key in ctx:
            ctx.pop(key, None)


def snapshot_meta(
    population: Optional[np.ndarray],
    objectives: Optional[np.ndarray],
    violations: Optional[np.ndarray],
    *,
    pareto_solutions: Optional[np.ndarray] = None,
    pareto_objectives: Optional[np.ndarray] = None,
    complete: bool = True,
) -> Dict[str, Any]:
    meta: Dict[str, Any] = {"complete": bool(complete)}
    if population is not None:
        meta["population_shape"] = list(np.asarray(population).shape)
        meta["population_size"] = int(np.asarray(population).shape[0]) if np.asarray(population).ndim >= 1 else 0
    if objectives is not None:
        meta["objectives_shape"] = list(np.asarray(objectives).shape)
    if violations is not None:
        meta["violations_shape"] = list(np.asarray(violations).shape)
    if pareto_solutions is not None:
        try:
            meta["pareto_solutions_shape"] = list(np.asarray(pareto_solutions).shape)
        except Exception:
            meta["pareto_solutions_shape"] = []
    if pareto_objectives is not None:
        try:
            meta["pareto_objectives_shape"] = list(np.asarray(pareto_objectives).shape)
        except Exception:
            meta["pareto_objectives_shape"] = []
    return meta


def build_snapshot_payload(
    population: Optional[np.ndarray],
    objectives: Optional[np.ndarray],
    violations: Optional[np.ndarray],
    *,
    pareto_solutions: Optional[np.ndarray] = None,
    pareto_objectives: Optional[np.ndarray] = None,
    history: Optional[Any] = None,
    decision_trace: Optional[Any] = None,
) -> Dict[str, Any]:
    data: Dict[str, Any] = {}

    pop_arr = None
    if population is not None:
        pop_arr = np.asarray(population, dtype=float)
        if pop_arr.ndim == 1:
            pop_arr = pop_arr.reshape(1, -1) if pop_arr.size > 0 else pop_arr.reshape(0, 0)
        data[KEY_POPULATION] = pop_arr

    if objectives is not None:
        obj_arr = np.asarray(objectives, dtype=float)
        if obj_arr.ndim == 1:
            obj_arr = obj_arr.reshape(-1, 1) if obj_arr.size > 0 else obj_arr.reshape(0, 0)
        data[KEY_OBJECTIVES] = obj_arr
    elif pop_arr is not None:
        data[KEY_OBJECTIVES] = np.zeros((int(pop_arr.shape[0]), 0), dtype=float)

    if violations is not None:
        data[KEY_CONSTRAINT_VIOLATIONS] = np.asarray(violations, dtype=float).reshape(-1)
    elif pop_arr is not None:
        data[KEY_CONSTRAINT_VIOLATIONS] = np.zeros((int(pop_arr.shape[0]),), dtype=float)

    if pareto_solutions is not None:
        try:
            data[KEY_PARETO_SOLUTIONS] = np.asarray(pareto_solutions, dtype=float)
        except Exception:
            data[KEY_PARETO_SOLUTIONS] = pareto_solutions
    if pareto_objectives is not None:
        try:
            data[KEY_PARETO_OBJECTIVES] = np.asarray(pareto_objectives, dtype=float)
        except Exception:
            data[KEY_PARETO_OBJECTIVES] = pareto_objectives
    if history is not None:
        data[KEY_HISTORY] = history
    if decision_trace is not None:
        data[KEY_DECISION_TRACE] = decision_trace
    return data


def build_snapshot_refs(
    *,
    key: str,
    backend: str,
    schema: str,
    meta: Dict[str, Any],
    has_pareto_solutions: bool,
    has_pareto_objectives: bool,
    has_history: bool,
    has_decision_trace: bool,
) -> Dict[str, Any]:
    refs: Dict[str, Any] = {
        KEY_SNAPSHOT_KEY: key,
        KEY_SNAPSHOT_BACKEND: backend,
        KEY_SNAPSHOT_SCHEMA: schema,
        KEY_SNAPSHOT_META: dict(meta or {}),
        KEY_POPULATION_REF: key,
        KEY_OBJECTIVES_REF: key,
        KEY_CONSTRAINT_VIOLATIONS_REF: key,
    }
    if has_pareto_solutions:
        refs[KEY_PARETO_SOLUTIONS_REF] = key
    if has_pareto_objectives:
        refs[KEY_PARETO_OBJECTIVES_REF] = key
    if has_history:
        refs[KEY_HISTORY_REF] = key
    if has_decision_trace:
        refs[KEY_DECISION_TRACE_REF] = key
    return refs
