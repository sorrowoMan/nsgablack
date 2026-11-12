"""Composition helpers for Adapter empty-proposal terminal semantics."""

from __future__ import annotations

from dataclasses import fields
from typing import Any, Iterable, Mapping

from blackbase.wire import thaw_wire_mapping

from ..core.state import StepOutcome


def _encode_dispatch_stop_outcome(outcome: StepOutcome | None) -> dict[str, Any] | None:
    """Encode the explicit global stop observed during an empty child call."""
    if outcome is None:
        return None
    if (not isinstance(outcome, StepOutcome) or outcome.committed
            or not (outcome.status == "cancelled" or outcome.stop_requested)):
        raise ValueError("dispatch stop requires a noncommitted cancellation or explicit stop")
    return {field.name: (thaw_wire_mapping(outcome.metadata) if field.name == "metadata"
                        else getattr(outcome, field.name)) for field in fields(StepOutcome)}


def _decode_dispatch_stop_outcome(payload: Mapping[str, Any] | None) -> StepOutcome | None:
    if payload is None:
        return None
    if not isinstance(payload, Mapping) or set(payload) != {field.name for field in fields(StepOutcome)}:
        raise ValueError("dispatch stop outcome fields mismatch")
    outcome = StepOutcome(**dict(payload))
    _encode_dispatch_stop_outcome(outcome)
    return outcome


def child_empty_proposal_outcome(
    adapter: Any,
    control: Any,
    context: Mapping[str, Any],
) -> StepOutcome | None:
    getter = getattr(adapter, "get_empty_proposal_outcome", None)
    if not callable(getter):
        return None
    outcome = getter(control, context)
    if outcome is not None and not isinstance(outcome, StepOutcome):
        raise TypeError(
            f"{type(adapter).__name__}.get_empty_proposal_outcome() must "
            "return StepOutcome or None"
        )
    if outcome is not None and outcome.committed:
        raise ValueError("an empty child proposal cannot commit a logical step")
    return outcome


def aggregate_named_empty_outcomes(
    rows: Iterable[tuple[str, StepOutcome | None]],
    *,
    owner: str,
) -> StepOutcome | None:
    values = tuple(rows)
    if not values:
        return None
    for _label, outcome in values:
        if outcome is not None and outcome.status == "cancelled":
            return StepOutcome(
                status="cancelled",
                reason=outcome.reason,
                metadata={"adapter": owner, "children": _child_audit(values)},
            )
    successes = [
        outcome
        for _label, outcome in values
        if outcome is not None
        and (
            outcome.reason == "goal_reached"
            or str(outcome.metadata.get("completion", "")) == "success"
        )
    ]
    if successes:
        return StepOutcome(
            status="terminal",
            reason="goal_reached",
            metadata={
                "adapter": owner,
                "completion": "success",
                "children": _child_audit(values),
            },
        )
    if all(outcome is not None and outcome.terminal for _label, outcome in values):
        exhausted = all(
            outcome is not None
            and (
                outcome.reason == "search_exhausted"
                or str(outcome.metadata.get("completion", "")) == "exhausted"
            )
            for _label, outcome in values
        )
        return StepOutcome(
            status="terminal",
            reason="search_exhausted" if exhausted else "composite_terminal",
            metadata={
                "adapter": owner,
                "completion": "exhausted" if exhausted else "terminal",
                "children": _child_audit(values),
            },
        )
    return None


def _child_audit(
    rows: Iterable[tuple[str, StepOutcome | None]],
) -> list[dict[str, Any]]:
    return [
        {
            "component": label,
            "status": "idle" if outcome is None else outcome.status,
            "reason": "" if outcome is None else outcome.reason,
        }
        for label, outcome in rows
    ]


__all__ = [
    "aggregate_named_empty_outcomes",
    "child_empty_proposal_outcome",
]
