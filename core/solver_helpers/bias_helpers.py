"""Bias module helper utilities."""

from __future__ import annotations

from typing import Any, Mapping, Optional

import numpy as np
from blackbase.call_binding import CallCandidate, invoke_bound_once
from blackbase.preferences import PreferenceDelta, PreferenceProvider, preserve_feedback_evidence


def project_bias_feedback(solver, feedback, violation, candidate, individual_id, context):
    """Build a selection view while preserving the measured feedback evidence."""
    from ..evaluation_feedback import copy_feedback_with_result

    raw = copy_feedback_with_result(feedback, objectives=feedback.objectives, violation=violation)
    # Per-candidate evaluation metrics must reach both legacy and declared
    # preference consumers without mutating shared hook/store context.
    context = dict(context or {})
    metrics = dict(context.get("metrics") or {})
    metrics.update(dict(raw.metrics or {}))
    context["metrics"] = metrics
    module = solver.bias_module
    provenance_getter = getattr(solver, "candidate_provenance_for", None)
    if callable(provenance_getter):
        # A row number alone is not candidate identity; a standalone evaluation
        # must not inherit the previous batch's token at that position.
        provenance = provenance_getter(candidate)
        if provenance is not None:
            from nsgablack.context_keys import KEY_CANDIDATE_TOKEN
            context[KEY_CANDIDATE_TOKEN] = provenance.candidate_token
    bind_runtime = getattr(module, "bind_runtime", None)
    if callable(bind_runtime):
        bind_runtime(solver)
    deltas = ()
    if isinstance(module, PreferenceProvider):
        deltas = tuple(module.preferences(candidate, raw, context))
        objectives = np.array(raw.objectives, copy=True)
        allowed = set(module.preference_keys)
        for delta in deltas:
            if not isinstance(delta, PreferenceDelta) or delta.key not in allowed:
                raise ValueError("bias preference writes an undeclared key")
            prefix, separator, index = delta.key.partition(".")
            if prefix != "objectives" or not separator or not index.isdecimal() or int(index) >= objectives.size:
                raise ValueError(f"bias cannot modify this selection key: {delta.key}")
            objectives[int(index)] += delta.delta
    else:
        objectives = solver._apply_bias(raw.objectives.copy(), candidate, individual_id, context)
    selected_violation = 0.0 if solver.ignore_constraint_violation_when_bias else float(violation)
    projected = copy_feedback_with_result(raw, objectives=objectives, violation=selected_violation)
    projected = preserve_feedback_evidence(
        raw, projected, raw_violation=violation, projected_violation=selected_violation,
        deltas=deltas, reason=f"bias:{type(module).__name__}",
    )
    return projected, np.asarray(objectives, dtype=float), selected_violation


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
            out = invoke_bound_once(
                apply_fn,
                (
                    CallCandidate(
                        args=(obj_arr,),
                        kwargs={"context": ctx},
                        label="with_context",
                    ),
                    CallCandidate(args=(obj_arr,), label="without_context"),
                ),
            )
            return np.asarray(out, dtype=float).reshape(-1)
    except Exception as exc:
        from ...bias.preferences import PreferenceContractError
        if isinstance(exc, PreferenceContractError):
            raise
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
