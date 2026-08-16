"""Bias module helper utilities."""

from __future__ import annotations

from typing import Any, Mapping, Optional

import numpy as np


def apply_bias_module(
    solver: Any,
    objectives: Any,
    x: Any = None,
    individual_id: Optional[int] = None,
    context: Optional[Mapping[str, Any]] = None,
    *,
    report_soft_error_fn: Any = None,
    logger: Any = None,
    normalize_bias_output_fn: Any = None,
) -> np.ndarray:
    """Apply a solver bias module to an objective vector."""
    bias_module = getattr(solver, "bias_module", None)
    obj_arr = np.asarray(objectives, dtype=float).reshape(-1)
    if bias_module is None:
        return obj_arr
    ctx = dict(context or {})
    try:
        vector_fn = getattr(bias_module, "compute_bias_vector", None)
        if callable(vector_fn):
            return np.asarray(
                vector_fn(x, obj_arr, individual_id=individual_id, context=ctx),
                dtype=float,
            ).reshape(-1)

        scalar_fn = getattr(bias_module, "compute_bias", None)
        if callable(scalar_fn):
            out = [
                scalar_fn(x, float(value), individual_id=individual_id, context=ctx)
                for value in obj_arr
            ]
            return np.asarray(out, dtype=float).reshape(-1)

        apply_fn = getattr(bias_module, "apply", None)
        if callable(apply_fn):
            try:
                out = apply_fn(obj_arr, context=ctx)
            except TypeError:
                out = apply_fn(obj_arr)
            return np.asarray(out, dtype=float).reshape(-1)
    except Exception as exc:
        if callable(report_soft_error_fn):
            report_soft_error_fn(
                component="SolverBase",
                event="apply_bias_module",
                exc=exc,
                logger=logger,
                context_store=getattr(solver, "context_store", None),
                strict=bool(getattr(solver, "plugin_strict", False)),
            )
        if bool(getattr(solver, "plugin_strict", False)):
            raise
    return obj_arr


__all__ = [
    "apply_bias_module",
]
