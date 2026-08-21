"""Snapshot helper utilities for SolverBase."""

from __future__ import annotations

import time
from typing import Any, Dict, Optional

from blackbase.context import SnapshotHandle, SnapshotRecord, SnapshotStore, create_snapshot_store, make_snapshot_key

from blackbase.context.context_keys import (
    KEY_BEST_X,
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


POPULATION_SNAPSHOT_SCHEMA_V2 = "nsgablack.population_snapshot/v2"
POPULATION_AUTHORITY_KEY = "population_authority"
POPULATION_PARTITIONS_KEY = "population_partitions"
LAST_EVALUATED_BATCH_KEY = "last_evaluated_batch"


class PartitionedPopulationSnapshotError(RuntimeError):
    """Raised when a single-population consumer sees partitioned authority."""


def population_snapshot_authority_mode(payload: Any) -> str:
    if not isinstance(payload, dict):
        return "single"
    authority = payload.get(POPULATION_AUTHORITY_KEY)
    if not isinstance(authority, dict):
        if POPULATION_PARTITIONS_KEY in payload or LAST_EVALUATED_BATCH_KEY in payload:
            return "partitioned"
        return "single"
    mode = str(authority.get("authority_mode", "single") or "single").strip().lower()
    if mode not in {"single", "partitioned", "step_batch"}:
        raise ValueError(f"unsupported population snapshot authority mode: {mode}")
    has_single_fields = any(
        key in payload
        for key in (KEY_POPULATION, KEY_OBJECTIVES, KEY_CONSTRAINT_VIOLATIONS)
    )
    if mode == "partitioned" and has_single_fields:
        raise ValueError(
            "partitioned population snapshot must not expose top-level "
            "population/objectives/constraint_violations"
        )
    if mode != "partitioned" and (
        POPULATION_PARTITIONS_KEY in payload or LAST_EVALUATED_BATCH_KEY in payload
    ):
        raise ValueError(
            "single/step_batch snapshot must not contain partition-only fields"
        )
    return mode


def require_single_population_payload(payload: Any) -> Dict[str, Any]:
    """Return the numeric payload unless its authority is partitioned."""

    if not isinstance(payload, dict):
        raise TypeError("population snapshot payload must be a dict")
    mode = population_snapshot_authority_mode(payload)
    if mode == "partitioned":
        raise PartitionedPopulationSnapshotError(
            "population authority is partitioned; consume population_partitions "
            "instead of treating last_evaluated_batch as one population"
        )
    return payload


def build_snapshot_payload(
    population: Any = None,
    objectives: Any = None,
    violations: Any = None,
    *,
    pareto_solutions: Any = None,
    pareto_objectives: Any = None,
    history: Any = None,
    decision_trace: Any = None,
) -> Dict[str, Any]:
    """Build canonical snapshot payload for large runtime objects."""
    out: Dict[str, Any] = {}
    if population is not None:
        out[KEY_POPULATION] = population
    if objectives is not None:
        out[KEY_OBJECTIVES] = objectives
    if violations is not None:
        out[KEY_CONSTRAINT_VIOLATIONS] = violations
    if pareto_solutions is not None:
        if isinstance(pareto_solutions, dict) and "individuals" in pareto_solutions:
            out[KEY_PARETO_SOLUTIONS] = pareto_solutions.get("individuals")
        else:
            out[KEY_PARETO_SOLUTIONS] = pareto_solutions
    if pareto_objectives is not None:
        out[KEY_PARETO_OBJECTIVES] = pareto_objectives
    if history is not None:
        out[KEY_HISTORY] = history
    if decision_trace is not None:
        out[KEY_DECISION_TRACE] = decision_trace
    return out


def build_snapshot_refs(
    *,
    key: str,
    backend: str,
    schema: str,
    meta: Optional[Dict[str, Any]] = None,
    has_pareto_solutions: bool = False,
    has_pareto_objectives: bool = False,
    has_history: bool = False,
    has_decision_trace: bool = False,
    authority_mode: str = "single",
) -> Dict[str, Any]:
    """Build lightweight context refs to snapshot payload."""
    refs = {
        KEY_SNAPSHOT_KEY: str(key),
        KEY_SNAPSHOT_BACKEND: str(backend),
        KEY_SNAPSHOT_SCHEMA: str(schema),
        KEY_SNAPSHOT_META: dict(meta or {}),
    }
    if str(authority_mode or "single") != "partitioned":
        refs.update(
            {
                KEY_POPULATION_REF: str(key),
                KEY_OBJECTIVES_REF: str(key),
                KEY_CONSTRAINT_VIOLATIONS_REF: str(key),
            }
        )
    if has_pareto_solutions:
        refs[KEY_PARETO_SOLUTIONS_REF] = str(key)
    if has_pareto_objectives:
        refs[KEY_PARETO_OBJECTIVES_REF] = str(key)
    if has_history:
        refs[KEY_HISTORY_REF] = str(key)
    if has_decision_trace:
        refs[KEY_DECISION_TRACE_REF] = str(key)
    return refs


def snapshot_meta(
    population: Any = None,
    objectives: Any = None,
    violations: Any = None,
    *,
    pareto_solutions: Any = None,
    pareto_objectives: Any = None,
    complete: bool = True,
) -> Dict[str, Any]:
    """Create compact snapshot metadata."""
    def _shape(value: Any):
        return list(getattr(value, "shape", ())) if value is not None else None

    return {
        "created_at": float(time.time()),
        "complete": bool(complete),
        "population_shape": _shape(population),
        "objectives_shape": _shape(objectives),
        "violations_shape": _shape(violations),
        "pareto_solutions_shape": _shape(pareto_solutions),
        "pareto_objectives_shape": _shape(pareto_objectives),
    }


def strip_large_context_fields(ctx: Dict[str, Any]) -> Dict[str, Any]:
    """Remove large runtime objects from context in-place."""
    for key in (
        KEY_BEST_X,
        KEY_POPULATION,
        KEY_OBJECTIVES,
        KEY_CONSTRAINT_VIOLATIONS,
        KEY_PARETO_SOLUTIONS,
        KEY_PARETO_OBJECTIVES,
        KEY_HISTORY,
        KEY_DECISION_TRACE,
    ):
        ctx.pop(key, None)
    return ctx


__all__ = [
    "SnapshotStore",
    "SnapshotHandle",
    "SnapshotRecord",
    "create_snapshot_store",
    "make_snapshot_key",
    "build_snapshot_payload",
    "build_snapshot_refs",
    "snapshot_meta",
    "strip_large_context_fields",
    "POPULATION_SNAPSHOT_SCHEMA_V2",
    "POPULATION_AUTHORITY_KEY",
    "POPULATION_PARTITIONS_KEY",
    "LAST_EVALUATED_BATCH_KEY",
    "PartitionedPopulationSnapshotError",
    "population_snapshot_authority_mode",
    "require_single_population_payload",
]
