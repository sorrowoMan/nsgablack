"""Owned state and recovery gate for one logical optimization run.

Solver compatibility attributes are views into this object. Process-local locks
and clocks never enter the portable RunProgressState checkpoint.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Callable, ClassVar, Mapping
import threading
import time
from .run_progress import RunProgressState


@dataclass
class RunSession:
    """Run accounting survives failed steps; result publication has its own seal.

    This owner is deliberately excluded from RuntimeTransaction. Attempts,
    elapsed time and consumed budgets must survive rollback. Locks and queued
    callbacks are process-local, never step snapshots or portable checkpoints.
    """

    rollback_exempt_reason: ClassVar[str] = (
        "run attempts, elapsed time and consumed budgets survive failed steps; "
        "logical steps advance only after commit and results use finalization publication"
    )

    run_id: str | None = None
    sequence: int = 0
    generation: int = 0
    running: bool = False
    stop_requested: bool = False
    stop_reason: str | None = None
    setup_complete: bool = False
    collecting_restore: bool = False
    applying_restore: bool = False
    restore_lock: Any = field(default_factory=threading.RLock, repr=False)
    pending_restore: list = field(default_factory=list, repr=False)
    resume_loaded: bool = False
    resume_cursor: int = 0
    steps: int = 0
    attempts: int = 0
    idle_attempts: int = 0
    elapsed: float = 0.0
    clock_started: float | None = None
    deadline_remaining: float | None = None
    result: Any = None
    last_step_outcome: Any = None
    finalizing: bool = False
    evaluation_budget: Any = None

    def submit_restore(self, apply: Callable[[], Any], *, generation: int, source: str) -> Any:
        with self.restore_lock:
            if self.running and not self.applying_restore:
                raise RuntimeError("state cannot mutate a running Solver outside the restore phase")
            if not self.setup_complete:
                self.queue_restore_envelope(apply, source=source)
                self.resume_cursor = max(0, int(generation))
                return None
            return apply()

    def mark_restored(self, generation: int) -> None:
        self.resume_cursor = max(0, int(generation))
        self.resume_loaded = True

    def step_limit(self, requested: int) -> int:
        return max(0, int(requested)) + (self.resume_cursor if self.resume_loaded or self.pending_restore else 0)

    def queue_restore_envelope(
        self,
        apply: Callable[[], None],
        *,
        source: str = "external",
    ) -> None:
        """Queue one restore transaction for the post-setup lifecycle slot."""

        if not callable(apply):
            raise TypeError("restore envelope apply callback must be callable")
        with self.restore_lock:
            if (
                bool(self.running) or bool(self.setup_complete)
            ) and not bool(self.collecting_restore):
                raise RuntimeError(
                    "restore envelopes may only be queued before runtime setup"
                )
            self.pending_restore.append((str(source), apply))

    def _apply_pending_restore_envelopes(self) -> None:
        with self.restore_lock:
            pending = list(self.pending_restore)
            self.pending_restore = []
            if len(pending) > 1:
                raise RuntimeError(
                    "multiple restore envelopes were queued for one Solver run: "
                    + ", ".join(source for source, _apply in pending)
                )
            self.applying_restore = True
            try:
                for _source, apply in pending:
                    apply()
            finally:
                self.applying_restore = False
        if pending and not bool(getattr(self, "resume_loaded", False)):
            raise RuntimeError(
                "restore envelope completed without establishing resume state"
            )

    def _start_run_progress_clock(self) -> None:
        if self.clock_started is None:
            self.clock_started = time.monotonic()

    def _pause_run_progress_clock(self) -> None:
        started = self.clock_started
        if started is None:
            return
        delta = max(0.0, float(time.monotonic() - started))
        self.elapsed += delta
        if self.deadline_remaining is not None:
            self.deadline_remaining = max(
                0.0,
                float(self.deadline_remaining) - delta,
            )
        self.clock_started = None

    def _record_completed_run_step(self) -> None:
        self.steps = int(self.steps) + 1

    def _record_run_step_attempt(self, status: str) -> None:
        self.attempts = int(self.attempts) + 1
        if str(status) in {"idle", "rejected"}:
            self.idle_attempts = (
                int(self.idle_attempts) + 1
            )
        else:
            self.idle_attempts = 0

    @property
    def run_progress_steps(self) -> int:
        return int(self.steps)

    @property
    def run_progress_attempts(self) -> int:
        return int(self.attempts)

    @property
    def run_progress_consecutive_idle_attempts(self) -> int:
        return int(self.idle_attempts)

    @property
    def run_progress_elapsed_seconds(self) -> float:
        elapsed = float(self.elapsed)
        if self.clock_started is not None:
            elapsed += max(
                0.0,
                float(time.monotonic() - self.clock_started),
            )
        return elapsed

    def export_run_progress_state(self) -> dict[str, Any]:
        remaining = self.deadline_remaining
        if (
            remaining is not None
            and self.clock_started is not None
        ):
            remaining = max(
                0.0,
                float(remaining)
                - float(time.monotonic() - self.clock_started),
            )
        return RunProgressState(
            steps_completed=self.run_progress_steps,
            attempts_completed=self.run_progress_attempts,
            consecutive_idle_attempts=self.run_progress_consecutive_idle_attempts,
            elapsed_seconds=self.run_progress_elapsed_seconds,
            deadline_remaining_seconds=remaining,
            run_id=self.run_id,
        ).as_dict()

    def restore_run_progress_state(
        self,
        payload: Mapping[str, Any] | None,
    ) -> None:
        if not isinstance(payload, Mapping):
            self.steps = 0
            self.attempts = 0
            self.idle_attempts = 0
            self.elapsed = 0.0
            self.clock_started = None
            self.deadline_remaining = None
            return
        state = RunProgressState.from_dict(payload)
        active_run_id = getattr(self, "run_id", None)
        if (
            state.run_id is not None
            and active_run_id is not None
            and str(state.run_id) != str(active_run_id)
        ):
            raise ValueError(
                "run progress state belongs to a different logical run: "
                f"progress={state.run_id!r}, solver={active_run_id!r}"
            )
        self.steps = state.steps_completed
        self.attempts = state.attempts_completed
        self.idle_attempts = (
            state.consecutive_idle_attempts
        )
        self.elapsed = state.elapsed_seconds
        self.clock_started = None
        self.deadline_remaining = (
            state.deadline_remaining_seconds
        )
