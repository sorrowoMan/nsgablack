from __future__ import annotations

import time
import threading
from dataclasses import dataclass
from typing import Any, Dict, List, Mapping, Optional

from ..base import Plugin
from blackbase.context import ContextEvent, detach_context_value, replay_context
from blackbase.context.context_keys import KEY_CONTEXT_EVENTS


@dataclass
class AsyncEventHubConfig:
    mode: str = "async"  # async | sync
    commit_policy: str = "generation_end"  # generation_end | manual
    max_pending: int = 10000
    drop_policy: str = "drop_old"  # drop_old | drop_new
    events_key: str = KEY_CONTEXT_EVENTS


class AsyncEventHubPlugin(Plugin):
    context_requires = ()
    context_provides = (KEY_CONTEXT_EVENTS,)
    context_mutates = (KEY_CONTEXT_EVENTS,)
    context_cache = ()
    context_notes = (
        "Queues async context events and commits them on policy; "
        "sync mode writes events directly to context."
    )
    """
    Asynchronous event hub for context updates.

    Purpose:
    - Provide a single place to queue/commit context events when plugins run async.
    - Enforce boundary semantics (generation-level commit).
    """

    def __init__(self, cfg: Optional[AsyncEventHubConfig] = None):
        super().__init__(name="async_event_hub")
        self.cfg = cfg or AsyncEventHubConfig()
        self.pending_events: List[Dict[str, Any]] = []
        self.committed_events: List[Dict[str, Any]] = []
        self.attempt_events: List[Dict[str, Any]] = []
        self.noncommitted_events: List[Dict[str, Any]] = []
        self.attempt_audit: List[Dict[str, Any]] = []
        self.current_generation: Optional[int] = None
        self.current_attempt: Optional[int] = None
        self._attempt_active = False
        self.last_commit_generation: Optional[int] = None
        self.last_committed_context: Optional[Dict[str, Any]] = None
        self.is_algorithmic = False
        self._lock = threading.RLock()
        self._commit_lock = threading.Lock()

    def on_step_attempt_start(self, attempt: int, logical_step: int):
        with self._lock:
            self.current_attempt = int(attempt)
            self.current_generation = int(logical_step)
            self.attempt_events = []
            self._attempt_active = True

    def on_generation_end(self, generation: int):
        # Commit only after the enclosing attempt has a final outcome.
        del generation

    def on_step_attempt_end(
        self,
        attempt: int,
        logical_step: int,
        outcome: Mapping[str, Any],
    ) -> None:
        with self._lock:
            outcome_dict = dict(outcome or {})
            status = str(outcome_dict.get("status", "unknown") or "unknown")
            committed = bool(outcome_dict.get("committed", False))
            finalized = [
                {
                    **event,
                    "attempt": int(attempt),
                    "attempt_status": status,
                    "attempt_committed": committed,
                }
                for event in self.attempt_events
            ]
            self._append_bounded(
                self.attempt_audit,
                {
                    "attempt": int(attempt),
                    "logical_step": int(logical_step),
                    "status": status,
                    "committed": committed,
                    "event_count": len(finalized),
                },
            )
            if committed:
                for event in finalized:
                    self._append_bounded(self.pending_events, event)
            else:
                for event in finalized:
                    self._append_bounded(self.noncommitted_events, event)
            self.attempt_events = []
            self._attempt_active = False
            self.current_attempt = None
            should_commit = (
                committed
                and self.cfg.commit_policy == "generation_end"
                and bool(self.pending_events)
            )
        if should_commit:
            # Includes events queued by background threads before this attempt.
            self.commit(generation=int(logical_step))

    def record_event(
        self,
        *,
        context: Optional[Dict[str, Any]] = None,
        kind: str,
        key: Optional[str],
        value: Any,
        source: Optional[str] = None,
        generation: Optional[int] = None,
        step: Optional[int] = None,
    ) -> None:
        with self._lock:
            # Attempt identity and queue selection are one atomic observation.
            # Reading these fields before acquiring the lock can attach an old
            # attempt id to an event queued in the next attempt.
            gen = generation if generation is not None else self.current_generation
            event = {
                **ContextEvent(
                    kind=str(kind),
                    key=key,
                    value=value,
                    timestamp=float(time.time()),
                    source=source,
                    generation=gen,
                    step=step,
                ).to_dict(),
                "attempt": self.current_attempt,
                "delivery_mode": str(self.cfg.mode),
            }
            if self._attempt_active:
                # Both modes are transactional inside an attempt.  A rejected
                # attempt must not mutate the caller's context.
                self._append_bounded(self.attempt_events, event)
                return
            if self.cfg.mode == "sync":
                if context is not None:
                    context.setdefault(self.cfg.events_key, []).append(
                        detach_context_value(
                            event,
                            path="async_event_hub.sync_event",
                        )
                    )
                self._append_bounded(self.committed_events, event)
                self.last_commit_generation = gen
                return
            self._append_bounded(self.pending_events, event)

    def _append_bounded(
        self,
        target: List[Dict[str, Any]],
        event: Dict[str, Any],
    ) -> None:
        if len(target) >= int(self.cfg.max_pending):
            if self.cfg.drop_policy == "drop_new":
                return
            if target:
                target.pop(0)
        target.append(event)

    def commit(self, *, context: Optional[Dict[str, Any]] = None, generation: Optional[int] = None) -> None:
        with self._commit_lock:
            self._commit_locked(context=context, generation=generation)

    def _commit_locked(
        self,
        *,
        context: Optional[Dict[str, Any]] = None,
        generation: Optional[int] = None,
    ) -> None:
        with self._lock:
            if not self.pending_events:
                return
            # Detach the exact queue object being committed.  Prefix deletion
            # is unsafe with a concurrent drop_old append: the old prefix may
            # already have been evicted and deleting by length would remove a
            # newly appended event instead.
            pending = self.pending_events
            self.pending_events = []

        base_context: Optional[Dict[str, Any]] = None
        if context is not None:
            base_context = dict(context)
        elif self.solver is not None and hasattr(self.solver, "get_context"):
            try:
                base_context = dict(self.solver.get_context())
            except Exception:
                base_context = None

        if base_context is None:
            self._restore_detached_events(pending)
            return

        try:
            committed = replay_context(base_context, pending, strict=True)
        except BaseException:
            self._restore_detached_events(pending)
            raise
        with self._lock:
            self.last_committed_context = committed
            for event in pending:
                self._append_bounded(self.committed_events, event)
            self.last_commit_generation = (
                generation if generation is not None else self.current_generation
            )

    def _restore_detached_events(self, detached: List[Dict[str, Any]]) -> None:
        """Requeue one failed commit batch without disturbing event order."""

        with self._lock:
            combined = [*detached, *self.pending_events]
            limit = max(0, int(self.cfg.max_pending))
            if limit == 0:
                self.pending_events = []
            elif len(combined) <= limit:
                self.pending_events = combined
            elif self.cfg.drop_policy == "drop_new":
                self.pending_events = combined[:limit]
            else:
                self.pending_events = combined[-limit:]

    def get_committed_context(self) -> Optional[Dict[str, Any]]:
        with self._lock:
            if self.last_committed_context is None:
                return None
            return detach_context_value(
                self.last_committed_context,
                path="async_event_hub.committed_context",
            )

    def get_report(self) -> Optional[Dict[str, Any]]:
        with self._lock:
            pending_count = len(self.pending_events)
            committed_count = len(self.committed_events)
            active_count = len(self.attempt_events)
            noncommitted_count = len(self.noncommitted_events)
            attempt_audit = list(self.attempt_audit)
            last_commit_generation = self.last_commit_generation
        return {
            "mode": self.cfg.mode,
            "commit_policy": self.cfg.commit_policy,
            "pending": pending_count,
            "committed": committed_count,
            "active_attempt_events": active_count,
            "noncommitted": noncommitted_count,
            "attempts": len(attempt_audit),
            "attempt_status_counts": {
                status: sum(
                    1
                    for record in attempt_audit
                    if str(record.get("status", "unknown")) == status
                )
                for status in sorted(
                    {
                        str(record.get("status", "unknown"))
                        for record in attempt_audit
                    }
                )
            },
            "last_commit_generation": last_commit_generation,
        }



