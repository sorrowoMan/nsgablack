"""
Async event-driven controller adapter.

This adapter keeps optimization flow in an event queue:
- enqueue "propose" events
- dispatch events to strategy adapters
- evaluate candidates (by solver)
- feed completion events back to strategies

It is compatible with ComposableSolver's synchronous step loop while keeping
event semantics explicit in context/state.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np

from .algorithm_adapter import AlgorithmAdapter
from ..utils.context.context_keys import (
    KEY_EVENT_ARCHIVE,
    KEY_EVENT_HISTORY,
    KEY_EVENT_INFLIGHT,
    KEY_EVENT_QUEUE,
    KEY_EVENT_SHARED,
)


@dataclass
class EventStrategySpec:
    """One event-driven strategy participant."""

    adapter: AlgorithmAdapter
    name: str
    weight: float = 1.0
    enabled: bool = True


@dataclass
class AsyncEventDrivenConfig:
    # Max candidates dispatched per solver step.
    total_batch_size: int = 32
    # Keep queue around this size.
    target_queue_size: int = 64
    # Initial queue fill per enabled strategy.
    bootstrap_events_per_strategy: int = 8
    # Queue capacity guard.
    max_queue_size: int = 4096
    # Queue overflow policy: "drop_old" | "drop_new".
    overflow_policy: str = "drop_old"

    # Objective aggregation for scalar score.
    objective_aggregation: str = "sum"  # "sum" | "first"
    violation_penalty: float = 1e6

    # Archive / logging limits.
    max_archive_size: int = 256
    max_event_history: int = 4096
    # Events to enqueue after each completion.
    refill_events_per_completion: int = 1


class AsyncEventDrivenAdapter(AlgorithmAdapter):
    """
    Event-driven orchestration adapter.

    Notes:
    - This adapter does not require generation-level synchronization semantics.
    - "Async" means event-level scheduling, compatible with sync or async
      evaluation backends.
    """

    context_requires = ("generation",)
    context_provides = (
        KEY_EVENT_QUEUE,
        KEY_EVENT_INFLIGHT,
        KEY_EVENT_ARCHIVE,
        KEY_EVENT_HISTORY,
        KEY_EVENT_SHARED,
    )
    context_mutates = (
        KEY_EVENT_QUEUE,
        KEY_EVENT_INFLIGHT,
        KEY_EVENT_ARCHIVE,
        KEY_EVENT_HISTORY,
        KEY_EVENT_SHARED,
    )
    context_cache = (KEY_EVENT_HISTORY, KEY_EVENT_INFLIGHT)
    context_notes = (
        "Queue-based event orchestration for multi-strategy propose/update.",
        "Provides queue/inflight/archive snapshots for replay and inspection.",
    )

    def __init__(
        self,
        strategies: Sequence[EventStrategySpec],
        *,
        config: Optional[AsyncEventDrivenConfig] = None,
        name: str = "async_event_driven",
        priority: int = 0,
    ) -> None:
        super().__init__(name=name, priority=priority)
        self.cfg = config or AsyncEventDrivenConfig()
        self.strategies = list(strategies)
        if not self.strategies:
            raise ValueError("AsyncEventDrivenAdapter requires at least one strategy.")

        self._step = 0
        self._event_id = 0
        self._queue: List[Dict[str, Any]] = []
        self._inflight: List[Dict[str, Any]] = []
        self.archive: List[Dict[str, Any]] = []
        self.event_history: List[Dict[str, Any]] = []
        self.shared_state: Dict[str, Any] = {}
        self._stats: Dict[str, Dict[str, float]] = {}
        self._solver_ref: Optional[Any] = None
        self._last_runtime_projection: Dict[str, Any] = {}
        self._rng = np.random.default_rng()

    def setup(self, solver: Any) -> None:
        self._solver_ref = solver
        self._step = 0
        self._event_id = 0
        self._queue = []
        self._inflight = []
        self.archive = []
        self.event_history = []
        self.shared_state = {}
        self._stats = {}
        self._last_runtime_projection = {}
        for spec in self.strategies:
            self._stats[spec.name] = {
                "proposed": 0.0,
                "completed": 0.0,
                "best_score": float("inf"),
            }
            spec.adapter.setup(solver)
        self._seed_queue()
        self._publish_state(solver)

    def teardown(self, solver: Any) -> None:
        for spec in self.strategies:
            spec.adapter.teardown(solver)
        self._solver_ref = None

    def propose(self, solver: Any, context: Dict[str, Any]) -> Sequence[np.ndarray]:
        self._topup_queue()

        batch = int(max(1, int(self.cfg.total_batch_size)))
        dispatch_count = min(batch, len(self._queue))
        out: List[np.ndarray] = []
        inflight: List[Dict[str, Any]] = []
        by_name = {s.name: s for s in self.strategies if s.enabled}

        for _ in range(dispatch_count):
            event = self._queue.pop(0)
            if event.get("type") != "propose":
                continue
            strategy_name = str(event.get("strategy", "")).strip()
            spec = by_name.get(strategy_name)
            if spec is None:
                continue

            budget = int(max(1, int(event.get("budget", 1))))
            local_ctx = dict(context)
            local_ctx["event_shared"] = self.shared_state
            local_ctx["event"] = dict(event)
            local_ctx["strategy"] = strategy_name
            local_ctx["step"] = int(self._step)

            proposed = self.coerce_candidates(spec.adapter.propose(solver, local_ctx))
            if not proposed:
                proposed = [solver.init_candidate(local_ctx)]

            for cand in proposed[:budget]:
                out.append(np.asarray(cand, dtype=float))
                inflight.append(
                    {
                        "event_id": int(event["event_id"]),
                        "strategy": strategy_name,
                        "dispatch_step": int(self._step),
                    }
                )
                self._stats[strategy_name]["proposed"] += 1.0

            self._log_event("dispatch", event_id=event["event_id"], strategy=strategy_name, budget=budget)

        self._inflight = inflight
        self._publish_state(solver)
        return out

    def update(
        self,
        solver: Any,
        candidates: Sequence[np.ndarray],
        objectives: np.ndarray,
        violations: np.ndarray,
        context: Dict[str, Any],
    ) -> None:
        if candidates is None or len(candidates) == 0:
            self._step += 1
            self._topup_queue()
            self._publish_state(solver)
            return

        groups: Dict[str, List[int]] = {}
        completion_events: List[Dict[str, Any]] = []
        for idx in range(len(candidates)):
            info = self._inflight[idx] if idx < len(self._inflight) else {}
            strategy_name = str(info.get("strategy", "unknown"))
            groups.setdefault(strategy_name, []).append(idx)

            vio = float(violations[idx]) if violations is not None else 0.0
            score = self._score(objectives[idx], vio)
            record = {
                "event_id": int(info.get("event_id", -1)),
                "strategy": strategy_name,
                "step": int(self._step),
                "score": float(score),
                "violation": float(vio),
            }
            completion_events.append(record)
            self._push_archive(
                {
                    **record,
                    "objective": np.asarray(objectives[idx], dtype=float),
                    "x": np.asarray(candidates[idx], dtype=float),
                }
            )
            if strategy_name in self._stats:
                self._stats[strategy_name]["completed"] += 1.0
                self._stats[strategy_name]["best_score"] = min(
                    float(self._stats[strategy_name]["best_score"]),
                    float(score),
                )
            self._log_event("completion", **record)

            refill = int(max(0, int(self.cfg.refill_events_per_completion)))
            for _ in range(refill):
                self._enqueue_propose(strategy=strategy_name, budget=1, source="completion")

        by_name = {s.name: s for s in self.strategies if s.enabled}
        for strategy_name, idxs in groups.items():
            spec = by_name.get(strategy_name)
            if spec is None:
                continue
            local_ctx = dict(context)
            local_ctx["event_shared"] = self.shared_state
            local_ctx["strategy"] = strategy_name
            local_ctx["completed_events"] = [completion_events[i] for i in idxs]
            spec.adapter.update(
                solver,
                [np.asarray(candidates[i], dtype=float) for i in idxs],
                np.asarray([objectives[i] for i in idxs], dtype=float),
                np.asarray([violations[i] for i in idxs], dtype=float),
                local_ctx,
            )

        self._inflight = []
        self._step += 1
        self._topup_queue()
        self._publish_state(solver)

    def _score(self, objectives_row: np.ndarray, violation: float) -> float:
        if self.cfg.objective_aggregation == "first":
            obj = float(objectives_row[0])
        else:
            obj = float(np.sum(objectives_row))
        return float(violation) * float(self.cfg.violation_penalty) + obj

    def _enabled_specs(self) -> List[EventStrategySpec]:
        return [s for s in self.strategies if bool(s.enabled)]

    def _seed_queue(self) -> None:
        enabled = self._enabled_specs()
        for spec in enabled:
            count = int(max(1, int(self.cfg.bootstrap_events_per_strategy)))
            for _ in range(count):
                self._enqueue_propose(strategy=spec.name, budget=1, source="bootstrap")

    def _topup_queue(self) -> None:
        target = int(max(1, int(self.cfg.target_queue_size)))
        missing = max(0, target - len(self._queue))
        if missing <= 0:
            return

        enabled = self._enabled_specs()
        if not enabled:
            return
        weights = np.asarray([max(0.0, float(s.weight)) for s in enabled], dtype=float)
        if float(np.sum(weights)) <= 0:
            weights = np.ones(len(enabled), dtype=float)
        probs = weights / float(np.sum(weights))

        for _ in range(missing):
            idx = int(self._rng.choice(len(enabled), p=probs))
            spec = enabled[idx]
            self._enqueue_propose(strategy=spec.name, budget=1, source="topup")

    def _enqueue_propose(self, *, strategy: str, budget: int, source: str) -> None:
        max_q = int(max(1, int(self.cfg.max_queue_size)))
        if len(self._queue) >= max_q:
            if str(self.cfg.overflow_policy).lower() == "drop_new":
                return
            if self._queue:
                dropped = self._queue.pop(0)
                self._log_event("drop", dropped_event_id=dropped.get("event_id"), reason="overflow")

        self._event_id += 1
        event = {
            "event_id": int(self._event_id),
            "type": "propose",
            "strategy": str(strategy),
            "budget": int(max(1, int(budget))),
            "source": str(source),
            "created_step": int(self._step),
        }
        self._queue.append(event)
        self._log_event("enqueue", event_id=event["event_id"], strategy=event["strategy"], source=source)

    def _push_archive(self, item: Dict[str, Any]) -> None:
        self.archive.append(item)
        self.archive.sort(key=lambda x: float(x.get("score", float("inf"))))
        limit = int(max(1, int(self.cfg.max_archive_size)))
        if len(self.archive) > limit:
            del self.archive[limit:]

    def _log_event(self, kind: str, **payload: Any) -> None:
        rec = {"kind": str(kind), "step": int(self._step), **payload}
        self.event_history.append(rec)
        limit = int(max(1, int(self.cfg.max_event_history)))
        if len(self.event_history) > limit:
            self.event_history = self.event_history[-limit:]

        solver = self._solver_ref
        if solver is None or not hasattr(solver, "get_plugin"):
            return
        try:
            hub = solver.get_plugin("async_event_hub")
        except Exception:
            hub = None
        if hub is None or not hasattr(hub, "record_event"):
            return
        try:
            hub.record_event(
                kind="set",
                key=f"event_stream.{kind}",
                value=rec,
                source=self.name,
                generation=getattr(solver, "generation", None),
                step=int(self._step),
            )
        except Exception:
            return

    def _publish_state(self, solver: Any) -> None:
        queue_snapshot = [
            {
                "event_id": int(e.get("event_id", -1)),
                "type": str(e.get("type", "")),
                "strategy": str(e.get("strategy", "")),
                "budget": int(e.get("budget", 1)),
                "source": str(e.get("source", "")),
            }
            for e in self._queue[:200]
        ]
        inflight_snapshot = [dict(x) for x in self._inflight[:200]]
        archive_snapshot = [
            {
                "event_id": int(a.get("event_id", -1)),
                "strategy": str(a.get("strategy", "")),
                "step": int(a.get("step", -1)),
                "score": float(a.get("score", float("inf"))),
                "violation": float(a.get("violation", 0.0)),
            }
            for a in self.archive[:200]
        ]
        stats = {}
        for name, val in self._stats.items():
            proposed = float(val.get("proposed", 0.0))
            completed = float(val.get("completed", 0.0))
            best_score = float(val.get("best_score", float("inf")))
            stats[name] = {
                "proposed": int(proposed),
                "completed": int(completed),
                "best_score": None if not np.isfinite(best_score) else best_score,
            }

        self.shared_state = {
            "step": int(self._step),
            "queue_size": int(len(self._queue)),
            "inflight_size": int(len(self._inflight)),
            "archive_size": int(len(self.archive)),
            "event_count": int(len(self.event_history)),
            "stats": stats,
            "queue": queue_snapshot,
            "inflight": inflight_snapshot,
            "archive": archive_snapshot,
        }
        _ = solver
        self._last_runtime_projection = {
            KEY_EVENT_SHARED: self.shared_state,
            KEY_EVENT_QUEUE: queue_snapshot,
            KEY_EVENT_INFLIGHT: inflight_snapshot,
            KEY_EVENT_ARCHIVE: archive_snapshot,
            KEY_EVENT_HISTORY: list(self.event_history),
        }

    def get_runtime_context_projection(self, solver: Any) -> Dict[str, Any]:
        _ = solver
        return dict(self._last_runtime_projection)

    def get_runtime_context_projection_sources(self, solver: Any) -> Dict[str, str]:
        _ = solver
        source = f"adapter.{self.__class__.__name__}"
        return {str(key): source for key in self._last_runtime_projection.keys()}

    def get_state(self) -> Dict[str, Any]:
        return {
            "step": int(self._step),
            "event_id": int(self._event_id),
            "queue": list(self._queue),
            "inflight": list(self._inflight),
            "archive": list(self.archive),
            "event_history": list(self.event_history),
            "stats": dict(self._stats),
        }

    def set_state(self, state: Dict[str, Any]) -> None:
        self._step = int(state.get("step", 0))
        self._event_id = int(state.get("event_id", 0))
        self._queue = list(state.get("queue", []))
        self._inflight = list(state.get("inflight", []))
        self.archive = list(state.get("archive", []))
        self.event_history = list(state.get("event_history", []))
        self._stats = dict(state.get("stats", {}))
