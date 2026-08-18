"""Result helper utilities."""

from __future__ import annotations

from typing import Any, Dict, Mapping, Optional


def format_run_result(
    solver: Any,
    *,
    base_result: Optional[Mapping[str, Any]] = None,
    context: Optional[Mapping[str, Any]] = None,
    return_dict: bool = True,
    return_experiment: bool = False,
    experiment_builder: Any = None,
    tuple_builder: Any = None,
) -> Any:
    """Format run output for base and EvolutionSolver callers."""
    if return_experiment and callable(experiment_builder):
        experiment = experiment_builder()
        if experiment is not None:
            return experiment

    result: Dict[str, Any] = dict(base_result or {})
    result.setdefault("generation", int(getattr(solver, "generation", 0) or 0))
    result.setdefault("evaluation_count", int(getattr(solver, "evaluation_count", 0) or 0))
    get_incumbent = getattr(solver, "get_incumbent", None)
    incumbent = get_incumbent() if callable(get_incumbent) else None
    if incumbent is not None:
        result.setdefault("best_solution", incumbent.candidate.copy())
        result.setdefault("best_objective", float(incumbent.score))
        result.setdefault("best_objectives", incumbent.objectives.copy())
        result.setdefault(
            "best_constraint_violation",
            float(incumbent.constraint_violation),
        )
        result.setdefault("incumbent", incumbent.as_dict())
    else:
        if getattr(solver, "best_x", None) is not None:
            result.setdefault("best_solution", getattr(solver, "best_x", None))
        if getattr(solver, "best_objective", None) is not None:
            result.setdefault("best_objective", getattr(solver, "best_objective", None))
        elif getattr(solver, "best_f", None) is not None:
            result.setdefault("best_objective", getattr(solver, "best_f", None))
    if hasattr(solver, "scalarizer_failure_policy"):
        result.setdefault(
            "scalarizer_failure_policy",
            getattr(solver, "scalarizer_failure_policy", None),
        )
        result.setdefault(
            "scalarizer_fallback_count",
            int(getattr(solver, "scalarizer_fallback_count", 0) or 0),
        )
        result.setdefault(
            "result_quality_degraded",
            getattr(solver, "result_quality_degraded", None),
        )
        result.setdefault(
            "scalarizer_audit_complete",
            bool(getattr(solver, "scalarizer_audit_complete", False)),
        )
    get_projection_audit = getattr(solver, "get_incumbent_projection_audit", None)
    if callable(get_projection_audit):
        projection_audit = dict(get_projection_audit() or {})
        for key, value in projection_audit.items():
            result.setdefault(str(key), value)
    get_runtime_projection_audit = getattr(
        solver,
        "get_runtime_projection_audit",
        None,
    )
    if callable(get_runtime_projection_audit):
        runtime_projection_audit = dict(get_runtime_projection_audit() or {})
        if runtime_projection_audit:
            result.setdefault(
                "runtime_projection_audit",
                runtime_projection_audit,
            )
    if context is not None:
        result["context"] = dict(context)

    if return_dict:
        return result
    if callable(tuple_builder):
        return tuple_builder()
    return result


__all__ = [
    "format_run_result",
]
