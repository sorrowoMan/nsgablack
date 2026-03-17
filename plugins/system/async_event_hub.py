from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Dict, List, Mapping, Optional

from ..base import Plugin
from ...core.state.context_events import record_context_event, replay_context
from ...utils.context.context_keys import KEY_CONTEXT_EVENTS


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
        self.current_generation: Optional[int] = None
        self.last_commit_generation: Optional[int] = None
        self.last_committed_context: Optional[Dict[str, Any]] = None
        self.is_algorithmic = False

    def on_generation_start(self, generation: int):
        self.current_generation = int(generation)

    def on_generation_end(self, generation: int):
        if self.cfg.commit_policy == "generation_end":
            self.commit(generation=int(generation))

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
        gen = generation if generation is not None else self.current_generation
        event = {
            "kind": str(kind),
            "key": key,
            "value": value,
            "timestamp": float(time.time()),
            "source": source,
            "generation": gen,
            "step": step,
        }

        if self.cfg.mode == "sync":
            if context is not None:
                record_context_event(
                    context,
                    kind=kind,
                    key=key,
                    value=value,
                    source=source,
                    generation=gen,
                    step=step,
                    events_key=self.cfg.events_key,
                )
            self.committed_events.append(event)
            self.last_commit_generation = gen
            return

        if len(self.pending_events) >= int(self.cfg.max_pending):
            if self.cfg.drop_policy == "drop_new":
                return
            if self.pending_events:
                self.pending_events.pop(0)
        self.pending_events.append(event)

    def commit(self, *, context: Optional[Dict[str, Any]] = None, generation: Optional[int] = None) -> None:
        if not self.pending_events:
            return

        base_context: Optional[Dict[str, Any]] = None
        if context is not None:
            base_context = dict(context)
        elif self.solver is not None and hasattr(self.solver, "get_context"):
            try:
                base_context = dict(self.solver.get_context())
            except Exception:
                base_context = None

        if base_context is None:
            return

        committed = replay_context(base_context, list(self.pending_events), strict=False)
        self.last_committed_context = committed
        self.committed_events.extend(self.pending_events)
        self.pending_events = []
        self.last_commit_generation = generation if generation is not None else self.current_generation

    def get_committed_context(self) -> Optional[Dict[str, Any]]:
        return self.last_committed_context

    def get_report(self) -> Optional[Dict[str, Any]]:
        return {
            "mode": self.cfg.mode,
            "commit_policy": self.cfg.commit_policy,
            "pending": len(self.pending_events),
            "committed": len(self.committed_events),
            "last_commit_generation": self.last_commit_generation,
        }



