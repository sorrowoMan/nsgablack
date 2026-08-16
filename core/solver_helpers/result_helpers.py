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
    if getattr(solver, "best_x", None) is not None:
        result.setdefault("best_solution", getattr(solver, "best_x", None))
    if getattr(solver, "best_objective", None) is not None:
        result.setdefault("best_objective", getattr(solver, "best_objective", None))
    elif getattr(solver, "best_f", None) is not None:
        result.setdefault("best_objective", getattr(solver, "best_f", None))
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
