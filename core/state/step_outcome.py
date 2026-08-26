"""Explicit outcome of one Solver step attempt."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping
import warnings

from blackbase.wire import freeze_wire_mapping, thaw_wire_mapping


STEP_OUTCOME_STATUSES = frozenset(
    {"committed", "idle", "rejected", "cancelled", "terminal"}
)


@dataclass(frozen=True)
class StepOutcome:
    """Separate a logical committed step from an empty execution attempt."""

    status: str = "committed"
    evaluations: int = 0
    proposals: int = 0
    stop_requested: bool = False
    reason: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        status = str(self.status or "committed").strip().lower()
        if status not in STEP_OUTCOME_STATUSES:
            raise ValueError(f"unsupported StepOutcome status: {status}")
        evaluations = int(self.evaluations)
        proposals = int(self.proposals)
        if evaluations < 0 or proposals < 0:
            raise ValueError("StepOutcome counts must be non-negative")
        stop_requested = bool(self.stop_requested)
        reason = str(self.reason or "")
        if status == "cancelled":
            # Cancellation is a terminal control outcome, never a successful
            # idle attempt.  Normalize the redundant flag here so every run
            # loop and external consumer observes the same semantics.
            stop_requested = True
            if not reason:
                reason = "cancelled"
        object.__setattr__(self, "status", status)
        object.__setattr__(self, "evaluations", evaluations)
        object.__setattr__(self, "proposals", proposals)
        object.__setattr__(self, "stop_requested", stop_requested)
        object.__setattr__(self, "reason", reason)
        object.__setattr__(
            self,
            "metadata",
            freeze_wire_mapping(self.metadata, path="step_outcome.metadata"),
        )

    @property
    def committed(self) -> bool:
        return self.status == "committed"

    @property
    def terminal(self) -> bool:
        return self.stop_requested or self.status in {"cancelled", "terminal"}

    def as_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "committed": self.committed,
            "terminal": self.terminal,
            "evaluations": self.evaluations,
            "proposals": self.proposals,
            "stop_requested": self.stop_requested,
            "reason": self.reason,
            "metadata": thaw_wire_mapping(self.metadata),
        }

    def with_metadata(self, **updates: Any) -> "StepOutcome":
        """Return the same outcome with additional wire-safe evidence."""

        metadata = thaw_wire_mapping(self.metadata)
        metadata.update(updates)
        return StepOutcome(
            status=self.status,
            evaluations=self.evaluations,
            proposals=self.proposals,
            stop_requested=self.stop_requested,
            reason=self.reason,
            metadata=metadata,
        )

    @classmethod
    def from_value(
        cls,
        value: Any,
        *,
        allow_legacy: bool = False,
    ) -> "StepOutcome":
        if isinstance(value, cls):
            return value
        if not allow_legacy:
            raise TypeError(
                "Solver.step() must return StepOutcome; legacy None/bool/Mapping "
                "conversion is disabled"
            )
        warnings.warn(
            "Legacy Solver.step() outcomes are deprecated; return StepOutcome explicitly",
            DeprecationWarning,
            stacklevel=2,
        )
        if value is None:
            return cls(
                status="committed",
                metadata={"legacy_none_outcome": True},
            )
        if isinstance(value, bool):
            return cls(status="committed" if value else "idle")
        if isinstance(value, Mapping):
            return cls(
                status=str(value.get("status", "committed")),
                evaluations=int(value.get("evaluations", 0) or 0),
                proposals=int(value.get("proposals", 0) or 0),
                stop_requested=bool(value.get("stop_requested", False)),
                reason=str(value.get("reason", "")),
                metadata=dict(value.get("metadata", {}) or {}),
            )
        raise TypeError(
            "legacy Solver.step() outcome must be Mapping, bool, or None"
        )


__all__ = ["STEP_OUTCOME_STATUSES", "StepOutcome"]
