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
    attempts_completed: int = 0
    consecutive_idle_attempts: int = 0
    elapsed_seconds: float = 0.0
    deadline_remaining_seconds: float | None = None
    run_id: str | None = None

    def __post_init__(self) -> None:
        steps = int(self.steps_completed)
        attempts = int(self.attempts_completed)
        consecutive_idle = int(self.consecutive_idle_attempts)
        elapsed = float(self.elapsed_seconds)
        remaining = (
            None
            if self.deadline_remaining_seconds is None
            else float(self.deadline_remaining_seconds)
        )
        if steps < 0:
            raise ValueError("RunProgressState.steps_completed must be non-negative")
        if attempts < steps:
            raise ValueError(
                "RunProgressState.attempts_completed must be at least steps_completed"
            )
        if consecutive_idle < 0 or consecutive_idle > attempts:
            raise ValueError(
                "RunProgressState.consecutive_idle_attempts must be within attempt count"
            )
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
        object.__setattr__(self, "attempts_completed", attempts)
        object.__setattr__(self, "consecutive_idle_attempts", consecutive_idle)
        object.__setattr__(self, "elapsed_seconds", elapsed)
        object.__setattr__(self, "deadline_remaining_seconds", remaining)
        object.__setattr__(
            self,
            "run_id",
            None if self.run_id is None else str(self.run_id),
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema": "nsgablack.run_progress/v2",
            "steps_completed": self.steps_completed,
            "attempts_completed": self.attempts_completed,
            "consecutive_idle_attempts": self.consecutive_idle_attempts,
            "elapsed_seconds": self.elapsed_seconds,
            "deadline_remaining_seconds": self.deadline_remaining_seconds,
            "run_id": self.run_id,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "RunProgressState":
        data = dict(payload or {})
        schema = str(data.get("schema", "nsgablack.run_progress/v1"))
        if schema not in {
            "nsgablack.run_progress/v1",
            "nsgablack.run_progress/v2",
        }:
            raise ValueError(f"unsupported run progress schema: {schema}")
        steps = int(data.get("steps_completed", 0) or 0)
        return cls(
            steps_completed=steps,
            attempts_completed=(
                steps
                if schema == "nsgablack.run_progress/v1"
                else int(data.get("attempts_completed", steps) or 0)
            ),
            consecutive_idle_attempts=(
                0
                if schema == "nsgablack.run_progress/v1"
                else int(data.get("consecutive_idle_attempts", 0) or 0)
            ),
            elapsed_seconds=float(data.get("elapsed_seconds", 0.0) or 0.0),
            deadline_remaining_seconds=data.get("deadline_remaining_seconds"),
            run_id=data.get("run_id"),
        )


__all__ = ["RunProgressState"]
