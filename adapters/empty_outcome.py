"""Composition helpers for Adapter empty-proposal terminal semantics."""

from __future__ import annotations

from typing import Any, Iterable, Mapping

from ..core.state import StepOutcome


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
