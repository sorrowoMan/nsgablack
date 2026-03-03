"""Bias integration helpers used by SolverBase."""

from __future__ import annotations

from typing import Any, Callable, Dict, Optional

import numpy as np


def _report_debug_soft_error(
    *,
    solver: Any,
    report_soft_error_fn: Callable[..., Any],
    logger: Any,
    event: str,
    exc: Exception,
) -> None:
    report_soft_error_fn(
        component="SolverBase",
        event=event,
        exc=exc,
        logger=logger,
        context_store=getattr(solver, "context_store", None),
        strict=False,
        level="debug",
    )


def apply_bias_module(
    solver: Any,
    obj: np.ndarray,
    x: np.ndarray,
    individual_id: Optional[int],
    context: Dict[str, Any],
    *,
    report_soft_error_fn: Callable[..., Any],
    logger: Any,
    normalize_bias_output_fn: Callable[..., float],
) -> np.ndarray:
    bias_module = getattr(solver, "bias_module", None)
    if bias_module is None:
        return obj

    setter = getattr(bias_module, "set_context_store", None)
    if callable(setter):
        try:
            setter(getattr(solver, "context_store", None))
        except Exception as exc:
            _report_debug_soft_error(
                solver=solver,
                report_soft_error_fn=report_soft_error_fn,
                logger=logger,
                event="bias_set_context_store",
                exc=exc,
            )

    snapshot_setter = getattr(bias_module, "set_snapshot_store", None)
    if callable(snapshot_setter):
        try:
            snapshot_setter(getattr(solver, "snapshot_store", None))
        except Exception as exc:
            _report_debug_soft_error(
                solver=solver,
                report_soft_error_fn=report_soft_error_fn,
                logger=logger,
                event="bias_set_snapshot_store",
                exc=exc,
            )

    if not hasattr(bias_module, "compute_bias"):
        return obj

    if obj.size == 1:
        biased = bias_module.compute_bias(x, float(obj[0]), individual_id, context=context)
        return np.array([normalize_bias_output_fn(biased, name="bias.compute_bias")], dtype=float)

    out = []
    for idx in range(obj.size):
        out.append(
            normalize_bias_output_fn(
                bias_module.compute_bias(x, float(obj[idx]), individual_id, context=context),
                name="bias.compute_bias",
            )
        )
    return np.asarray(out, dtype=float)
