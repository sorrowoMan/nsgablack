"""Snapshot helper utilities for SolverBase."""

from __future__ import annotations

import time
from typing import Any, Dict, Mapping, Optional

import numpy as np
from blackbase.types import CandidateBatch

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
LAST_EVALUATION_EVENT_KEY = "last_evaluation_event"
LAST_EVALUATION_DISPOSITION_KEY = "last_evaluation_disposition"
CANDIDATE_BATCH_KEY = "candidate_batch"
CANDIDATE_PROVENANCE_KEY = "candidate_provenance"
CANDIDATE_PARTITIONS_SCHEMA_V1 = "nsgablack.candidate_population_partitions/v1"


class PartitionedPopulationSnapshotError(RuntimeError):
    """Raised when a single-population consumer sees partitioned authority."""


def _validate_candidate_identity(
    *,
    batch_payload: Any,
    provenance_payload: Any,
    numeric_population: np.ndarray,
    expected_tokens: tuple[str | None, ...] | None,
    seen_tokens: set[str],
) -> None:
    if not isinstance(batch_payload, Mapping):
        raise ValueError("authoritative population snapshot requires CandidateBatch")
    batch = CandidateBatch.from_dict(batch_payload)
    if (
        batch.numeric_matrix.shape != numeric_population.shape
        or not np.array_equal(
            batch.numeric_matrix,
            numeric_population,
            equal_nan=True,
        )
    ):
        raise ValueError(
            "authoritative CandidateBatch does not match numeric population"
        )
    tokens = tuple(batch.candidate_tokens)
    if expected_tokens is not None and tokens != expected_tokens:
        raise ValueError("authoritative candidate tokens disagree across views")
    if any(token is None for token in tokens):
        raise ValueError("authoritative candidate tokens must not be missing")
    normalized = tuple(str(token) for token in tokens)
    if len(set(normalized)) != len(normalized):
        raise ValueError("authoritative candidate tokens must be unique")
    duplicate = seen_tokens.intersection(normalized)
    if duplicate:
        raise ValueError(
            "candidate tokens are duplicated across population partitions: "
            f"{sorted(duplicate)!r}"
        )
    seen_tokens.update(normalized)
    if not isinstance(provenance_payload, (list, tuple)):
        raise ValueError("authoritative population snapshot requires provenance")
    from ..state.incumbent import CandidateProvenance

    provenance = tuple(
        CandidateProvenance.from_dict(item) for item in provenance_payload
    )
    if len(provenance) != len(normalized):
        raise ValueError("authoritative candidate provenance is misaligned")
    if tuple(item.candidate_token for item in provenance) != normalized:
        raise ValueError(
            "authoritative candidate tokens disagree with provenance lineage"
        )


def validate_population_snapshot_v2(
    payload: Any,
    *,
    snapshot_schema: str,
    expected_authority_mode: str | None = None,
    require_semantic_identity: bool = True,
) -> str:
    """Validate one authoritative ``population_snapshot/v2`` payload.

    Content digests prove immutability, not semantic legitimacy.  This validator
    closes the latter boundary for Evaluation Evidence settlement.
    """

    if str(snapshot_schema or "") != POPULATION_SNAPSHOT_SCHEMA_V2:
        raise ValueError(
            "authoritative population Snapshot record must use "
            f"{POPULATION_SNAPSHOT_SCHEMA_V2}"
        )
    if not isinstance(payload, Mapping):
        raise TypeError("population snapshot payload must be a Mapping")
    data = dict(payload)
    authority = data.get(POPULATION_AUTHORITY_KEY)
    if not isinstance(authority, Mapping):
        raise ValueError("population snapshot is missing population_authority")
    if str(authority.get("schema", "")) != POPULATION_SNAPSHOT_SCHEMA_V2:
        raise ValueError("population authority declares an unsupported schema")
    mode = population_snapshot_authority_mode(data)
    expected = str(expected_authority_mode or "").strip().lower()
    if expected and expected != mode:
        raise ValueError(
            "evaluation disposition authority mode does not match destination "
            f"Snapshot: expected={expected!r}, observed={mode!r}"
        )

    seen_tokens: set[str] = set()
    if mode == "partitioned":
        partition_envelope = data.get(POPULATION_PARTITIONS_KEY)
        if not isinstance(partition_envelope, Mapping):
            raise ValueError(
                "partitioned authority requires population_partitions envelope"
            )
        if (
            str(partition_envelope.get("schema", ""))
            != CANDIDATE_PARTITIONS_SCHEMA_V1
        ):
            raise ValueError("unsupported candidate population partitions schema")
        if str(partition_envelope.get("authority_mode", "")) != "partitioned":
            raise ValueError("partition envelope does not declare partitioned authority")
        items = tuple(partition_envelope.get("partitions", ()) or ())
        if not items:
            raise ValueError("partitioned authority requires at least one partition")
        from ...adapters.algorithm_adapter import PopulationPartition

        partition_ids: set[str] = set()
        for raw_item in items:
            if not isinstance(raw_item, Mapping):
                raise TypeError("population partition entry must be a Mapping")
            partition = PopulationPartition.from_dict(
                dict(raw_item.get("partition", {}) or {})
            )
            if partition.partition_id in partition_ids:
                raise ValueError("population partition IDs must be unique")
            partition_ids.add(partition.partition_id)
            if require_semantic_identity:
                _validate_candidate_identity(
                    batch_payload=raw_item.get("batch"),
                    provenance_payload=raw_item.get("provenance"),
                    numeric_population=partition.population,
                    expected_tokens=tuple(partition.candidate_tokens),
                    seen_tokens=seen_tokens,
                )
        return mode

    required = (KEY_POPULATION, KEY_OBJECTIVES, KEY_CONSTRAINT_VIOLATIONS)
    if any(key not in data for key in required):
        raise ValueError(
            "single/step_batch authority requires population, objectives and "
            "constraint_violations"
        )
    population = np.asarray(data[KEY_POPULATION], dtype=float)
    objectives = np.asarray(data[KEY_OBJECTIVES], dtype=float)
    violations = np.asarray(data[KEY_CONSTRAINT_VIOLATIONS], dtype=float).reshape(-1)
    if population.ndim == 1:
        population = (
            population.reshape(1, -1)
            if population.size
            else population.reshape(0, 0)
        )
    if objectives.ndim == 1:
        objectives = (
            objectives.reshape(-1, 1)
            if objectives.size
            else objectives.reshape(0, 0)
        )
    if population.ndim != 2 or objectives.ndim != 2:
        raise ValueError("population and objectives must be two-dimensional")
    if not (
        population.shape[0] == objectives.shape[0] == violations.shape[0]
    ):
        raise ValueError("population, objectives and violations must align by row")
    if require_semantic_identity:
        _validate_candidate_identity(
            batch_payload=data.get(CANDIDATE_BATCH_KEY),
            provenance_payload=data.get(CANDIDATE_PROVENANCE_KEY),
            numeric_population=population,
            expected_tokens=None,
            seen_tokens=seen_tokens,
        )
    return mode


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
    "LAST_EVALUATION_EVENT_KEY",
    "LAST_EVALUATION_DISPOSITION_KEY",
    "CANDIDATE_BATCH_KEY",
    "CANDIDATE_PROVENANCE_KEY",
    "validate_population_snapshot_v2",
    "PartitionedPopulationSnapshotError",
    "population_snapshot_authority_mode",
    "require_single_population_payload",
]
