"""Checkpointable logical-run progress for the shared Solver control plane."""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any, Mapping


@dataclass(frozen=True)
class RunProgressState:
    """Portable progress of one logical run.

    Wall-clock implementations must persist accumulated active duration, never
    a process-local ``monotonic()`` timestamp.  A restored Solver starts a new
    local clock and continues from :attr:`elapsed_seconds`.
    """

    steps_completed: int = 0
    elapsed_seconds: float = 0.0
    deadline_remaining_seconds: float | None = None
    run_id: str | None = None

    def __post_init__(self) -> None:
        steps = int(self.steps_completed)
        elapsed = float(self.elapsed_seconds)
        remaining = (
            None
            if self.deadline_remaining_seconds is None
            else float(self.deadline_remaining_seconds)
        )
        if steps < 0:
            raise ValueError("RunProgressState.steps_completed must be non-negative")
        if not math.isfinite(elapsed) or elapsed < 0.0:
            raise ValueError(
                "RunProgressState.elapsed_seconds must be finite and non-negative"
            )
        if remaining is not None:
            if not math.isfinite(remaining):
                raise ValueError(
                    "RunProgressState.deadline_remaining_seconds must be finite"
                )
            if remaining < 0.0:
                remaining = 0.0
        object.__setattr__(self, "steps_completed", steps)
        object.__setattr__(self, "elapsed_seconds", elapsed)
        object.__setattr__(self, "deadline_remaining_seconds", remaining)
        object.__setattr__(
            self,
            "run_id",
            None if self.run_id is None else str(self.run_id),
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema": "nsgablack.run_progress/v1",
            "steps_completed": self.steps_completed,
            "elapsed_seconds": self.elapsed_seconds,
            "deadline_remaining_seconds": self.deadline_remaining_seconds,
            "run_id": self.run_id,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "RunProgressState":
        data = dict(payload or {})
        schema = str(data.get("schema", "nsgablack.run_progress/v1"))
        if schema != "nsgablack.run_progress/v1":
            raise ValueError(f"unsupported run progress schema: {schema}")
        return cls(
            steps_completed=int(data.get("steps_completed", 0) or 0),
            elapsed_seconds=float(data.get("elapsed_seconds", 0.0) or 0.0),
            deadline_remaining_seconds=data.get("deadline_remaining_seconds"),
            run_id=data.get("run_id"),
        )


__all__ = ["RunProgressState"]
