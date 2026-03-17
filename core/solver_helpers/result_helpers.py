"""Result formatting helpers for solver run outputs."""

from __future__ import annotations

from typing import Any, Callable, Dict, Optional


def format_run_result(
    *,
    solver: Any,
    base_result: Dict[str, Any],
    return_dict: bool = False,
    return_experiment: bool = False,
    experiment_builder: Optional[Callable[[], Any]] = None,
    tuple_builder: Optional[Callable[[], Any]] = None,
) -> Any:
    """Normalize run() return types without re-implementing the loop."""
    _ = solver
    if return_experiment and callable(experiment_builder):
        return experiment_builder()
    if return_dict:
        return base_result
    if callable(tuple_builder):
        return tuple_builder()
    return base_result
