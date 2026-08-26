"""Optimization-semantic projection into the shared SolverResult codec."""

from __future__ import annotations

import json
from dataclasses import replace
from typing import Any, Mapping

import numpy as np

from blackbase.resources import DataRef
from blackbase.types import (
    PopulationSnapshot,
    SolveQuality,
    SolverResult,
    UnknownState,
    decode_shared_value,
)


DEFAULT_CASE_RESULT_INLINE_MAX_BYTES = 64 * 1024

_REPORT_FIELDS = (
    "status",
    "generation",
    "steps",
    "steps_executed",
    "resume_from",
    "evaluation_count",
    "elapsed_sec",
)


def build_solver_result(solver: Any, raw_output: Any) -> SolverResult:
    """Build a stable Case payload without changing direct ``Solver.run`` APIs.

    A formal ``SolverResult`` is passed through. Otherwise this boundary only
    exports a complete authoritative incumbent; it never reconstructs a best
    solution from partial mirror fields or scalarizes a population.
    """

    formal = _formal_solver_result(raw_output)
    result = (
        _align_formal_solver_result(solver, formal)
        if formal is not None
        else _build_declared_solver_result(solver, raw_output)
    )
    result = _merge_incumbent_projection_audit(solver, result)
    result = _merge_runtime_projection_audit(solver, result)
    result = _merge_runtime_artifact_refs(solver, result)
    return _apply_inline_gates(solver, result)


def _formal_solver_result(raw_output: Any) -> SolverResult | None:
    if isinstance(raw_output, SolverResult):
        return raw_output
    if not isinstance(raw_output, Mapping):
        return None
    if str(raw_output.get("protocol_type", "")) == "blackbase.solver_result":
        return SolverResult.from_dict(raw_output)
    nested = raw_output.get("solver_result")
    if isinstance(nested, SolverResult):
        return nested
    if (
        isinstance(nested, Mapping)
        and str(nested.get("protocol_type", "")) == "blackbase.solver_result"
    ):
        return SolverResult.from_dict(nested)
    return None


def _incumbent_provenance_payload(incumbent: Any) -> dict[str, Any]:
    if incumbent is None:
        return {}
    return {
        "candidate_token": incumbent.candidate_token,
        "evaluation_id": incumbent.evaluation_id,
        "source": incumbent.source,
        "source_run_id": incumbent.source_run_id,
        "warm_start_id": incumbent.warm_start_id,
        "proposal_id": incumbent.proposal_id,
    }


def _align_formal_solver_result(solver: Any, result: SolverResult) -> SolverResult:
    """Reject split authority and enrich a formal result with incumbent identity."""

    incumbent = _solver_incumbent(solver)
    if incumbent is None:
        return result
    canonical_solution = _declared_best_solution(solver)
    canonical_provenance = _incumbent_provenance_payload(incumbent)
    if (
        result.best_candidate_token is not None
        and result.best_candidate_token != incumbent.candidate_token
    ):
        raise RuntimeError("formal SolverResult best token disagrees with incumbent")
    if (
        result.best_evaluation_id is not None
        and result.best_evaluation_id != incumbent.evaluation_id
    ):
        raise RuntimeError("formal SolverResult evaluation identity disagrees with incumbent")
    if result.best_provenance and dict(result.best_provenance) != canonical_provenance:
        raise RuntimeError("formal SolverResult provenance disagrees with incumbent")
    if result.best_objectives is not None and not np.array_equal(
        np.asarray(result.best_objectives, dtype=float),
        incumbent.objectives,
        equal_nan=True,
    ):
        raise RuntimeError("formal SolverResult objectives disagree with incumbent")
    if (
        result.best_constraint_violation is not None
        and float(result.best_constraint_violation)
        != float(incumbent.constraint_violation)
    ):
        raise RuntimeError("formal SolverResult violation disagrees with incumbent")
    if result.best_solution_ref is not None:
        authoritative_ref = _coerce_ref(
            getattr(solver, "best_solution_ref", None)
            or getattr(solver, "best_state_ref", None)
        )
        if authoritative_ref is None or result.best_solution_ref != authoritative_ref:
            raise RuntimeError(
                "formal SolverResult best_solution_ref is not bound to the incumbent"
            )
    elif result.best_solution is not None:
        if not isinstance(result.best_solution, UnknownState):
            raise RuntimeError(
                "formal SolverResult inline best solution must be UnknownState"
            )
        if result.best_solution.as_dict() != canonical_solution.as_dict():
            raise RuntimeError("formal SolverResult best solution disagrees with incumbent")
    return replace(
        result,
        best_solution=(
            result.best_solution
            if result.best_solution_ref is not None or result.best_solution is not None
            else canonical_solution
        ),
        best_objectives=(
            result.best_objectives
            if result.best_objectives is not None
            else incumbent.objectives.copy()
        ),
        best_constraint_violation=(
            result.best_constraint_violation
            if result.best_constraint_violation is not None
            else float(incumbent.constraint_violation)
        ),
        best_candidate_token=incumbent.candidate_token,
        best_evaluation_id=incumbent.evaluation_id,
        best_provenance=canonical_provenance,
    )


def _merge_incumbent_projection_audit(
    solver: Any,
    result: SolverResult,
) -> SolverResult:
    getter = getattr(solver, "get_incumbent_projection_audit", None)
    if not callable(getter):
        return result
    audit = dict(getter() or {})
    if not audit:
        return result
    return replace(
        result,
        metadata={
            **dict(result.metadata or {}),
            **audit,
        },
    )


def _merge_runtime_projection_audit(
    solver: Any,
    result: SolverResult,
) -> SolverResult:
    getter = getattr(solver, "get_runtime_projection_audit", None)
    if not callable(getter):
        return result
    audit = dict(getter() or {})
    if not audit:
        return result
    return replace(
        result,
        metadata={
            **dict(result.metadata or {}),
            "runtime_projection_audit": audit,
        },
    )


def _build_declared_solver_result(solver: Any, raw_output: Any) -> SolverResult:
    population = _matrix(getattr(solver, "population", None))
    objectives = _objective_matrix(getattr(solver, "objectives", None))
    violations = _violation_vector(
        getattr(solver, "constraint_violations", None),
        rows=None if objectives is None else objectives.shape[0],
    )
    best_solution = _declared_best_solution(solver)
    best_objectives = _declared_best_objectives(solver)
    best_violation = _declared_best_violation(solver)
    best_solution_ref = _coerce_ref(
        getattr(solver, "best_solution_ref", None)
        or getattr(solver, "best_state_ref", None)
    )
    pareto_front = _pareto_front(solver, population, violations)
    pareto_front_ref = _coerce_ref(getattr(solver, "pareto_front_ref", None))
    history_ref = _coerce_ref(getattr(solver, "history_ref", None))

    source = dict(raw_output) if isinstance(raw_output, Mapping) else {}
    last_result = getattr(solver, "last_result", None)
    if isinstance(last_result, Mapping):
        source.update(dict(last_result))
    report = {key: source[key] for key in _REPORT_FIELDS if key in source}
    report.setdefault("generation", int(getattr(solver, "generation", 0) or 0))
    report.setdefault(
        "evaluation_count",
        int(getattr(solver, "evaluation_count", 0) or 0),
    )
    history = tuple(getattr(solver, "history", ()) or ())
    incumbent = _solver_incumbent(solver)
    solve_status, termination_reason, feasibility, quality = _solve_semantics(
        solver,
        source,
        best_solution=best_solution,
        best_solution_ref=best_solution_ref,
        best_violation=best_violation,
        pareto_front=pareto_front,
        pareto_front_ref=pareto_front_ref,
    )

    objective_count = 0
    if best_objectives is not None:
        objective_count = int(best_objectives.size)
    elif pareto_front is not None and pareto_front.objectives.ndim == 2:
        objective_count = int(pareto_front.objectives.shape[1])

    return SolverResult(
        best_solution=(
            None if best_solution_ref is not None else _protocol_solution(best_solution)
        ),
        best_solution_ref=best_solution_ref,
        best_objectives=best_objectives,
        best_constraint_violation=best_violation,
        best_candidate_token=(
            None if incumbent is None else incumbent.candidate_token
        ),
        best_evaluation_id=(None if incumbent is None else incumbent.evaluation_id),
        best_provenance=_incumbent_provenance_payload(incumbent),
        pareto_front=None if pareto_front_ref is not None else pareto_front,
        pareto_front_ref=pareto_front_ref,
        solve_status=solve_status,
        termination_reason=termination_reason,
        feasibility=feasibility,
        quality=quality,
        # Full history is a large runtime object.  It is only exposed through
        # a real provider/snapshot ref; never copied into the Case envelope.
        history=(),
        history_ref=history_ref,
        report=report,
        metadata={
            "framework": "nsgablack",
            "solver_class": type(solver).__name__,
            "objective_count": objective_count,
            "pareto_size": 0 if pareto_front is None else len(pareto_front.candidates),
            "history_length": len(history),
            "incumbent_policy_id": (
                None if incumbent is None else incumbent.policy_id
            ),
            "incumbent_evaluation_id": (
                None if incumbent is None else incumbent.evaluation_id
            ),
            "incumbent_candidate_token": (
                None if incumbent is None else incumbent.candidate_token
            ),
            "incumbent_warm_start_id": (
                None if incumbent is None else incumbent.warm_start_id
            ),
            "incumbent_proposal_id": (
                None if incumbent is None else incumbent.proposal_id
            ),
            "incumbent_source": None if incumbent is None else incumbent.source,
            "incumbent_source_run_id": (
                None if incumbent is None else incumbent.source_run_id
            ),
            "scalarizer_failure_policy": getattr(
                solver,
                "scalarizer_failure_policy",
                None,
            ),
            "scalarizer_fallback_count": int(
                getattr(solver, "scalarizer_fallback_count", 0) or 0
            ),
            "result_quality_degraded": getattr(
                solver,
                "result_quality_degraded",
                None,
            ),
            "scalarizer_audit_complete": bool(
                getattr(solver, "scalarizer_audit_complete", False)
            ),
        },
    )


def _solve_semantics(
    solver: Any,
    source: Mapping[str, Any],
    *,
    best_solution: Any,
    best_solution_ref: DataRef | None,
    best_violation: float | None,
    pareto_front: PopulationSnapshot | None,
    pareto_front_ref: DataRef | None,
) -> tuple[str, str, str, SolveQuality]:
    raw_status = str(source.get("status", "") or "").strip().lower()
    feasibility = str(
        source.get("feasibility", getattr(solver, "feasibility", "unknown"))
        or "unknown"
    ).strip().lower()
    if feasibility == "unknown":
        feasibility = _result_feasibility(best_violation, pareto_front)

    explicit_status = source.get("solve_status", getattr(solver, "solve_status", None))
    if explicit_status is not None:
        solve_status = str(explicit_status).strip().lower()
    elif raw_status == "stopped":
        solve_status = "stopped"
    elif raw_status in {"failed", "error"}:
        solve_status = "failed"
    elif feasibility == "feasible" and (
        best_solution is not None
        or best_solution_ref is not None
        or pareto_front is not None
        or pareto_front_ref is not None
    ):
        solve_status = "feasible"
    elif feasibility == "infeasible":
        solve_status = "infeasible"
    else:
        solve_status = "unknown"

    explicit_reason = source.get(
        "termination_reason",
        getattr(solver, "termination_reason", None),
    )
    if explicit_reason is not None:
        termination_reason = str(explicit_reason).strip().lower()
    elif raw_status == "stopped":
        termination_reason = "user_stop"
    elif raw_status in {"ok", "succeeded", "success"}:
        termination_reason = "completed"
    elif raw_status in {"failed", "error"}:
        termination_reason = "backend_failure"
    else:
        termination_reason = "unknown"

    raw_quality = source.get("quality", getattr(solver, "solve_quality", None))
    if isinstance(raw_quality, SolveQuality):
        quality = raw_quality
    elif isinstance(raw_quality, Mapping):
        quality = SolveQuality.from_dict(raw_quality)
    else:
        quality = SolveQuality()
    return solve_status, termination_reason, feasibility, quality


def _result_feasibility(
    best_violation: float | None,
    pareto_front: PopulationSnapshot | None,
) -> str:
    if best_violation is not None:
        return "feasible" if float(best_violation) <= 0.0 else "infeasible"
    if pareto_front is None or pareto_front.constraints is None:
        return "unknown"
    constraints = np.asarray(pareto_front.constraints, dtype=float)
    if constraints.size == 0:
        return "unknown"
    if constraints.ndim == 1:
        feasible_rows = constraints <= 0.0
    else:
        feasible_rows = np.all(constraints <= 0.0, axis=1)
    return "feasible" if bool(np.any(feasible_rows)) else "infeasible"


def _declared_best_solution(solver: Any) -> Any:
    incumbent = _solver_incumbent(solver)
    if incumbent is not None:
        semantic_metadata: dict[str, Any] = {}
        raw_metadata = incumbent.metadata.get("candidate.semantic_metadata")
        if isinstance(raw_metadata, Mapping):
            decoded = decode_shared_value(dict(raw_metadata))
            if isinstance(decoded, Mapping):
                semantic_metadata = dict(decoded)
        return UnknownState(
            values=incumbent.candidate.copy(),
            metadata=semantic_metadata,
        )
    return None


def _declared_best_objectives(solver: Any) -> np.ndarray | None:
    incumbent = _solver_incumbent(solver)
    if incumbent is not None:
        return incumbent.objectives.copy()
    return None


def _declared_best_violation(solver: Any) -> float | None:
    incumbent = _solver_incumbent(solver)
    if incumbent is not None:
        return float(incumbent.constraint_violation)
    return None


def _solver_incumbent(solver: Any) -> Any:
    getter = getattr(solver, "get_incumbent", None)
    return getter() if callable(getter) else None


def _pareto_front(
    solver: Any,
    population: np.ndarray | None,
    violations: np.ndarray | None,
) -> PopulationSnapshot | None:
    formal = getattr(solver, "pareto_population_snapshot", None)
    if isinstance(formal, Mapping):
        formal = PopulationSnapshot.from_dict(formal)
    if formal is None:
        raw_solutions = getattr(solver, "pareto_solutions", None)
        solutions = (
            raw_solutions.get("individuals")
            if isinstance(raw_solutions, Mapping)
            else raw_solutions
        )
        solution_matrix = _matrix(solutions)
        if solution_matrix is not None and solution_matrix.shape[0] > 0:
            raise RuntimeError(
                "Pareto result has numeric rows but no token-aligned "
                "PopulationSnapshot; refusing to infer semantic identity by value"
            )
        return None
    if not isinstance(formal, PopulationSnapshot):
        raise TypeError("pareto_population_snapshot must be PopulationSnapshot")
    if any(token is None for token in formal.candidate_tokens):
        raise RuntimeError(
            "nsgablack Pareto result requires a stable token for every candidate"
        )
    raw_solutions = getattr(solver, "pareto_solutions", None)
    solutions = (
        raw_solutions.get("individuals")
        if isinstance(raw_solutions, Mapping)
        else raw_solutions
    )
    solution_matrix = _matrix(solutions)
    if solution_matrix is not None:
        semantic_matrix = np.stack(
            [candidate.as_array().reshape(-1) for candidate in formal.candidates],
            axis=0,
        ) if formal.candidates else np.empty((0, 0), dtype=float)
        if (
            semantic_matrix.shape != solution_matrix.shape
            or not np.array_equal(semantic_matrix, solution_matrix, equal_nan=True)
        ):
            raise RuntimeError(
                "token-aligned Pareto Snapshot disagrees with the numeric Pareto view"
            )
    raw_objectives = _objective_matrix(getattr(solver, "pareto_objectives", None))
    if raw_objectives is not None and (
        raw_objectives.shape != formal.objectives.shape
        or not np.array_equal(raw_objectives, formal.objectives, equal_nan=True)
    ):
        raise RuntimeError(
            "token-aligned Pareto Snapshot disagrees with Pareto objectives"
        )
    return formal


def _merge_runtime_artifact_refs(solver: Any, result: SolverResult) -> SolverResult:
    merged = dict(result.artifact_refs)
    runtime = getattr(solver, "case_runtime", None)
    visible_runtime_refs = {
        **dict(getattr(runtime, "artifact_refs", {}) or {}),
        **dict(getattr(runtime, "finalization_artifact_refs", {}) or {}),
    }
    for key, value in visible_runtime_refs.items():
        if isinstance(value, DataRef):
            merged[str(key)] = value
    for key, value in dict(getattr(solver, "result_artifact_refs", {}) or {}).items():
        ref = _coerce_ref(value)
        if ref is not None:
            merged[str(key)] = ref
    if merged == dict(result.artifact_refs):
        return result
    return replace(result, artifact_refs=merged)


def _apply_inline_gates(solver: Any, result: SolverResult) -> SolverResult:
    limit = max(
        0,
        int(
            getattr(
                solver,
                "case_result_inline_max_bytes",
                DEFAULT_CASE_RESULT_INLINE_MAX_BYTES,
            )
            or 0
        ),
    )
    if result.best_solution_ref is None and result.best_solution is not None:
        encoded_best = result.as_dict()["best_solution"]
        result = _externalize_result_field(
            solver,
            result,
            field_name="best_solution",
            encoded_value=encoded_best,
            size_bytes=_encoded_size(encoded_best),
            limit=limit,
            kind="solution",
            protocol_type="blackbase.unknown_state",
        )
    if result.pareto_front_ref is None and result.pareto_front is not None:
        encoded_front = result.pareto_front.as_dict()
        result = _externalize_result_field(
            solver,
            result,
            field_name="pareto_front",
            encoded_value=encoded_front,
            size_bytes=_encoded_size(encoded_front),
            limit=limit,
            kind="pareto_front",
            protocol_type="blackbase.population_snapshot",
        )
    return result


def _encoded_size(value: Any) -> int:
    return len(
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    )


def _externalize_result_field(
    solver: Any,
    result: SolverResult,
    *,
    field_name: str,
    encoded_value: Any,
    size_bytes: int,
    limit: int,
    kind: str,
    protocol_type: str,
) -> SolverResult:
    if size_bytes <= limit:
        return result
    existing_ref = result.artifact_refs.get(field_name)
    if existing_ref is not None:
        return replace(
            result,
            **{field_name: None, f"{field_name}_ref": existing_ref},
        )
    runtime = getattr(solver, "case_runtime", None)
    publish = getattr(runtime, "publish_artifact", None)
    if not callable(publish):
        raise RuntimeError(
            f"SolverResult.{field_name} is {size_bytes} bytes and exceeds the inline "
            f"limit {limit}; "
            "run the Solver through a Project artifact authority or attach a formal provider"
        )
    ref = publish(
        field_name,
        encoded_value,
        serializer="json",
        kind=kind,
        media_type="application/json",
        metadata={
            "protocol_type": protocol_type,
            "inline_size_bytes": size_bytes,
        },
    )
    metadata = dict(result.metadata)
    metadata[f"{field_name}_inline_size_bytes"] = size_bytes
    return replace(
        result,
        **{
            field_name: None,
            f"{field_name}_ref": ref,
            "artifact_refs": {**dict(result.artifact_refs), field_name: ref},
        },
        metadata=metadata,
    )


def _protocol_solution(value: Any) -> Any:
    if value is None or isinstance(value, UnknownState):
        return value
    vector = _numeric_vector(value)
    if vector is not None:
        return UnknownState(vector, metadata={"source": "nsgablack.best_solution"})
    return value


def _matrix(value: Any) -> np.ndarray | None:
    if value is None:
        return None
    try:
        array = np.asarray(value, dtype=float)
    except (TypeError, ValueError):
        return None
    if array.ndim == 1:
        array = array.reshape(1, -1)
    return array if array.ndim == 2 else None


def _objective_matrix(value: Any) -> np.ndarray | None:
    if value is None:
        return None
    try:
        array = np.asarray(value, dtype=float)
    except (TypeError, ValueError):
        return None
    if array.ndim == 1:
        array = array.reshape(-1, 1)
    return array if array.ndim == 2 else None


def _violation_vector(value: Any, *, rows: int | None) -> np.ndarray | None:
    if value is None:
        return None
    try:
        array = np.asarray(value, dtype=float).reshape(-1)
    except (TypeError, ValueError):
        return None
    if rows is not None and array.shape[0] != rows:
        return None
    return array


def _numeric_vector(value: Any) -> np.ndarray | None:
    if isinstance(value, UnknownState):
        return value.as_array().reshape(-1)
    if value is None or isinstance(value, Mapping):
        return None
    try:
        array = np.asarray(value, dtype=float)
    except (TypeError, ValueError):
        return None
    return array.reshape(-1) if array.ndim <= 1 else None


def _coerce_ref(value: Any) -> DataRef | None:
    if value is None or isinstance(value, DataRef):
        return value
    if isinstance(value, Mapping):
        return DataRef.from_dict(value)
    raise TypeError(f"expected DataRef-compatible value, got {type(value).__name__}")


__all__ = ["DEFAULT_CASE_RESULT_INLINE_MAX_BYTES", "build_solver_result"]
