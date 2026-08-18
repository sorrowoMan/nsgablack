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
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

import numpy as np
from blackbase.contracts import BatchDisposition
from blackbase.context import RuntimeContextProjection

from ..algorithm_adapter import AlgorithmAdapter
from ..runtime_projection import aggregate_adapter_runtime_projections
from blackbase.context.context_keys import (
    KEY_EVENT_ARCHIVE,
    KEY_EVENT_HISTORY,
    KEY_EVENT_INFLIGHT,
    KEY_EVENT_QUEUE,
    KEY_EVENT_SHARED,
    KEY_GENERATION,
)


@dataclass
class EventStrategySpec:
    """One event-driven strategy participant."""

    adapter: AlgorithmAdapter
    name: str
    weight: float = 1.0
    enabled: bool = True


@dataclass
class EventCaseSpec(EventStrategySpec):
    """One signal-driven event router case.

    `EventStrategySpec` keeps the legacy queue-based semantics: enabled
    strategies are sampled into the event queue by weight.

    `EventCaseSpec` adds rule-router semantics on top of the same event queue:
    at each propose step, the adapter evaluates enabled cases against the
    runtime context, selects the highest-priority eligible case, then fills the
    queue with events for that selected case only.
    """

    when: Optional[Callable[[Dict[str, Any]], bool]] = None
    when_dsl: Optional[Dict[str, Any]] = None
    priority: int = 0
    cooldown_generations: int = 0
    min_active_generations: int = 0
    report_fields: Sequence[str] = ()


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
    context_contract_encapsulates_children = True
    state_recovery_level = "L1"
    state_recovery_notes = "Restores queue/inflight/archive/history snapshots; external side effects are not replayed."

    def __init__(
        self,
        strategies: Sequence[EventStrategySpec],
        *,
        config: Optional[AsyncEventDrivenConfig] = None,
        name: str = "async_event_driven",
        priority: int = 0,
        **config_kwargs,
    ) -> None:
        super().__init__(name=name, priority=priority)
        self.config = self.resolve_config(
            config=config,
            config_cls=AsyncEventDrivenConfig,
            config_kwargs=config_kwargs,
            adapter_name="AsyncEventDrivenAdapter",
        )
        self.cfg = self.config
        self.strategies = list(strategies)
        if not self.strategies:
            raise ValueError("AsyncEventDrivenAdapter requires at least one strategy.")
        strategy_names = [str(spec.name) for spec in self.strategies]
        if len(strategy_names) != len(set(strategy_names)):
            raise ValueError("AsyncEventDrivenAdapter strategy names must be unique")

        self._step = 0
        self._event_id = 0
        self._queue: List[Dict[str, Any]] = []
        self._inflight: List[Dict[str, Any]] = []
        self._last_allocations: List[
            Tuple[AlgorithmAdapter, int, int, Dict[str, Any]]
        ] = []
        self.archive: List[Dict[str, Any]] = []
        self.event_history: List[Dict[str, Any]] = []
        self.shared_state: Dict[str, Any] = {}
        self._stats: Dict[str, Dict[str, float]] = {}
        self._solver_ref: Optional[Any] = None
        self._last_runtime_projection: Dict[str, Any] = {}
        self._last_projection_writers: Dict[str, str] = {}
        self._active_case_name: Optional[str] = None
        self._active_case_since: Optional[int] = None
        self._case_last_exit: Dict[str, int] = {}
        self._last_event_decision: Dict[str, Any] = {}
        self._rng = np.random.default_rng()

    def setup(self, control: Any) -> None:
        self._solver_ref = control
        self._step = 0
        self._event_id = 0
        self._queue = []
        self._inflight = []
        self._last_allocations = []
        self.archive = []
        self.event_history = []
        self.shared_state = {}
        self._stats = {}
        self._last_runtime_projection = {}
        self._last_projection_writers = {}
        self._active_case_name = None
        self._active_case_since = None
        self._case_last_exit = {}
        self._last_event_decision = {}
        for spec in self.strategies:
            self._stats[spec.name] = {
                "proposed": 0.0,
                "completed": 0.0,
                "best_score": float("inf"),
            }
            spec.adapter.setup(control)
        if not self._uses_event_cases():
            self._seed_queue()
        self._publish_state(control)

    def teardown(self, control: Any) -> None:
        for spec in self.strategies:
            spec.adapter.teardown(control)
        self._solver_ref = None

    def propose(self, control: Any, context: Dict[str, Any]) -> Sequence[np.ndarray]:
        active_specs = self._enabled_specs()
        if self._uses_event_cases():
            active_specs, decision = self._select_event_case(context)
            self._last_event_decision = decision
            self._log_event("decision", **decision)
            active_names = {str(spec.name) for spec in active_specs}
            if set(self._event_strategy_names()) != active_names:
                self._queue = []
            self._topup_queue(active_specs)
        else:
            self._topup_queue(active_specs)

        batch = int(max(1, int(self.cfg.total_batch_size)))
        dispatch_count = min(batch, len(self._queue))
        by_name = {s.name: s for s in active_specs if s.enabled}
        pending: List[Tuple[EventStrategySpec, Dict[str, Any], int]] = []
        for _ in range(dispatch_count):
            event = self._queue.pop(0)
            if event.get("type") != "propose":
                continue
            strategy_name = str(event.get("strategy", "")).strip()
            spec = by_name.get(strategy_name)
            if spec is None:
                continue
            budget = int(max(1, int(event.get("budget", 1))))
            pending.append((spec, event, budget))

        grouped: Dict[str, Dict[str, Any]] = {}
        order: List[str] = []
        for spec, event, budget in pending:
            name = str(spec.name)
            if name not in grouped:
                grouped[name] = {"spec": spec, "events": [], "budget": 0}
                order.append(name)
            grouped[name]["events"].append((event, budget))
            grouped[name]["budget"] = int(grouped[name]["budget"]) + budget

        out: List[np.ndarray] = []
        inflight: List[Dict[str, Any]] = []
        allocations: List[Tuple[AlgorithmAdapter, int, int, Dict[str, Any]]] = []
        for strategy_name in order:
            group = grouped[strategy_name]
            spec = group["spec"]
            event_rows = list(group["events"])
            total_budget = int(group["budget"])
            first_event = dict(event_rows[0][0])
            local_ctx = dict(context)
            local_ctx["event_shared"] = self.shared_state
            local_ctx["event"] = first_event
            local_ctx["events"] = [dict(event) for event, _budget in event_rows]
            local_ctx["event_case"] = first_event.get("case")
            local_ctx["strategy"] = strategy_name
            local_ctx["step"] = int(self._step)

            proposed = self.coerce_candidates(spec.adapter.propose(control, local_ctx))
            selected = proposed[:total_budget]
            if len(selected) < len(proposed):
                spec.adapter.on_proposal_disposition(
                    control,
                    BatchDisposition.prefix(
                        proposed_count=len(proposed),
                        accepted_count=len(selected),
                        reason="event_budget",
                        metadata={"strategy": strategy_name},
                    ),
                    local_ctx,
                )

            event_slots = [
                event
                for event, event_budget in event_rows
                for _ in range(int(event_budget))
            ]
            start = len(out)
            accepted_by_event: Dict[int, int] = {}
            for cand, event in zip(selected, event_slots):
                out.append(np.asarray(cand, dtype=float))
                inflight.append(
                    {
                        "event_id": int(event["event_id"]),
                        "strategy": strategy_name,
                        "case": str(event.get("case", strategy_name)),
                        "dispatch_step": int(self._step),
                    }
                )
                self._stats[strategy_name]["proposed"] += 1.0
                event_id = int(event["event_id"])
                accepted_by_event[event_id] = accepted_by_event.get(event_id, 0) + 1
            end = len(out)
            if end > start:
                allocations.append((spec.adapter, start, end, dict(local_ctx)))
            for event, event_budget in event_rows:
                self._log_event(
                    "dispatch",
                    event_id=event["event_id"],
                    strategy=strategy_name,
                    budget=int(event_budget),
                    accepted=int(accepted_by_event.get(int(event["event_id"]), 0)),
                )

        self._inflight = inflight
        self._last_allocations = allocations
        self._publish_state(control)
        return out

    def on_proposal_disposition(
        self,
        control: Any,
        disposition: BatchDisposition,
        context: Dict[str, Any],
    ) -> None:
        if disposition.proposed_count != len(self._inflight):
            raise ValueError(
                "event disposition does not match inflight candidates: "
                f"proposed_count={disposition.proposed_count}, "
                f"inflight_count={len(self._inflight)}"
            )
        self._inflight = [self._inflight[index] for index in disposition.accepted_indices]
        reconciled: List[Tuple[AlgorithmAdapter, int, int, Dict[str, Any]]] = []
        cursor = 0
        for adapter, start, end, proposal_context in self._last_allocations:
            child = disposition.for_range(start, end)
            child_context = dict(context)
            child_context.update(proposal_context)
            adapter.on_proposal_disposition(control, child, child_context)
            if child.accepted_count == 0:
                continue
            next_cursor = cursor + child.accepted_count
            reconciled.append((adapter, cursor, next_cursor, proposal_context))
            cursor = next_cursor
        self._last_allocations = reconciled

    def update(
        self,
        control: Any,
        candidates: Sequence[np.ndarray],
        feedback: Tuple[np.ndarray, np.ndarray],
        context: Dict[str, Any],
    ) -> None:
        objectives, violations = feedback
        if len(candidates) != len(self._inflight):
            raise ValueError(
                "event feedback does not match inflight candidates: "
                f"candidates={len(candidates)}, inflight={len(self._inflight)}"
            )
        if len(objectives) != len(candidates) or len(violations) != len(candidates):
            raise ValueError("event candidate, objective, and violation counts must match")
        if len(candidates) == 0:
            self._step += 1
            if not self._uses_event_cases():
                self._topup_queue()
            self._publish_state(control)
            return

        groups: Dict[str, List[int]] = {}
        completion_events: List[Dict[str, Any]] = []
        for idx in range(len(candidates)):
            info = self._inflight[idx]
            strategy_name = str(info["strategy"])
            groups.setdefault(strategy_name, []).append(idx)

            vio = float(violations[idx])
            score = self._score(objectives[idx], vio)
            record = {
                "event_id": int(info["event_id"]),
                "strategy": strategy_name,
                "case": str(info["case"]),
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
        proposal_contexts = {
            str(proposal_context["strategy"]): proposal_context
            for _adapter, _start, _end, proposal_context in self._last_allocations
        }
        for strategy_name, idxs in groups.items():
            spec = by_name.get(strategy_name)
            if spec is None:
                raise RuntimeError(
                    f"inflight feedback references unknown strategy '{strategy_name}'"
                )
            proposal_context = proposal_contexts.get(strategy_name)
            if proposal_context is None:
                raise RuntimeError(
                    f"inflight feedback has no proposal context for strategy '{strategy_name}'"
                )
            local_ctx = dict(proposal_context)
            local_ctx.update(context)
            local_ctx["event_shared"] = self.shared_state
            local_ctx["strategy"] = strategy_name
            local_ctx["completed_events"] = [completion_events[i] for i in idxs]
            spec.adapter.update(
                control,
                [np.asarray(candidates[i], dtype=float) for i in idxs],
                (np.asarray([objectives[i] for i in idxs], dtype=float),
                 np.asarray([violations[i] for i in idxs], dtype=float)),
                local_ctx,
            )

        self._inflight = []
        self._last_allocations = []
        self._step += 1
        if not self._uses_event_cases():
            self._topup_queue()
        self._publish_state(control)

    def _score(self, objectives_row: np.ndarray, violation: float) -> float:
        if self.cfg.objective_aggregation == "first":
            obj = float(objectives_row[0])
        else:
            obj = float(np.sum(objectives_row))
        return float(violation) * float(self.cfg.violation_penalty) + obj

    def _uses_event_cases(self) -> bool:
        return any(isinstance(s, EventCaseSpec) for s in self.strategies)

    def _enabled_specs(self) -> List[EventStrategySpec]:
        return [s for s in self.strategies if bool(s.enabled)]

    @staticmethod
    def _get_by_path(obj: Any, path: str, default: Any = None) -> Any:
        if path is None:
            return default
        text = str(path).strip()
        if not text:
            return default
        if isinstance(obj, dict) and text in obj:
            return obj.get(text)
        cur = obj
        for part in text.split("."):
            if isinstance(cur, dict):
                if part not in cur:
                    return default
                cur = cur.get(part)
                continue
            if hasattr(cur, part):
                cur = getattr(cur, part)
                continue
            return default
        return cur

    def _resolve_condition_token(self, token: Any, context: Dict[str, Any]) -> Any:
        if isinstance(token, dict) and "var" in token:
            return self._get_by_path(context, str(token.get("var")), None)
        if isinstance(token, str) and token.startswith("$"):
            return self._get_by_path(context, token[1:], None)
        return token

    def _eval_condition_dsl(self, expr: Any, context: Dict[str, Any]) -> bool:
        if expr is None:
            return True
        if not isinstance(expr, dict):
            return bool(self._resolve_condition_token(expr, context))
        if "all" in expr:
            return all(self._eval_condition_dsl(item, context) for item in list(expr.get("all") or []))
        if "any" in expr:
            return any(self._eval_condition_dsl(item, context) for item in list(expr.get("any") or []))
        if "not" in expr:
            return not self._eval_condition_dsl(expr.get("not"), context)

        op_map = {
            "eq": lambda a, b: a == b,
            "ne": lambda a, b: a != b,
            "gt": lambda a, b: a > b,
            "ge": lambda a, b: a >= b,
            "lt": lambda a, b: a < b,
            "le": lambda a, b: a <= b,
            "in": lambda a, b: a in b,
            "not_in": lambda a, b: a not in b,
        }
        for op, fn in op_map.items():
            if op not in expr:
                continue
            pair = expr.get(op)
            if not isinstance(pair, (list, tuple)) or len(pair) != 2:
                return False
            left = self._resolve_condition_token(pair[0], context)
            right = self._resolve_condition_token(pair[1], context)
            try:
                return bool(fn(left, right))
            except Exception:
                return False
        return bool(expr)

    def _case_matches(self, spec: EventStrategySpec, context: Dict[str, Any]) -> bool:
        if not bool(getattr(spec, "enabled", True)):
            return False
        if not isinstance(spec, EventCaseSpec):
            return True
        if callable(spec.when):
            try:
                return bool(spec.when(dict(context)))
            except Exception:
                return False
        if isinstance(spec.when_dsl, dict):
            try:
                return bool(self._eval_condition_dsl(spec.when_dsl, dict(context)))
            except Exception:
                return False
        return True

    def _event_generation(self, context: Dict[str, Any]) -> int:
        raw = context.get(KEY_GENERATION, self._step)
        try:
            return int(raw)
        except Exception:
            return int(self._step)

    def _event_case_priority(self, spec: EventStrategySpec) -> int:
        return int(getattr(spec, "priority", 0) or 0)

    def _event_case_report(self, spec: EventStrategySpec, context: Dict[str, Any]) -> Dict[str, Any]:
        fields = tuple(getattr(spec, "report_fields", ()) or ())
        return {str(field): self._get_by_path(context, str(field), None) for field in fields}

    def _event_strategy_names(self) -> Tuple[str, ...]:
        return tuple(str(item.get("strategy", "")) for item in self._queue if str(item.get("strategy", "")))

    def _select_event_case(self, context: Dict[str, Any]) -> Tuple[List[EventStrategySpec], Dict[str, Any]]:
        enabled = self._enabled_specs()
        generation = self._event_generation(context)
        matched = [spec for spec in enabled if self._case_matches(spec, context)]
        order = {id(spec): idx for idx, spec in enumerate(enabled)}
        matched_sorted = sorted(
            matched,
            key=lambda spec: (self._event_case_priority(spec), -int(order.get(id(spec), 0))),
            reverse=True,
        )

        blocked: List[Dict[str, Any]] = []
        selected: Optional[EventStrategySpec] = None
        selected_reason = "matched"

        current = next((s for s in enabled if str(s.name) == str(self._active_case_name)), None)
        current_name = None if current is None else str(current.name)
        current_since = self._active_case_since
        if current is not None and current_since is not None:
            min_active = int(getattr(current, "min_active_generations", 0) or 0)
            if min_active > 0 and int(generation) < int(current_since) + min_active:
                selected = current
                selected_reason = "min_active_generations"

        if selected is None:
            for spec in matched_sorted:
                name = str(spec.name)
                if name == current_name:
                    selected = spec
                    selected_reason = "already_active"
                    break
                cooldown = int(getattr(spec, "cooldown_generations", 0) or 0)
                last_exit = self._case_last_exit.get(name)
                if cooldown > 0 and last_exit is not None and int(generation) < int(last_exit) + cooldown:
                    blocked.append(
                        {
                            "name": name,
                            "reason": "cooldown",
                            "remaining": int(last_exit) + int(cooldown) - int(generation),
                        }
                    )
                    continue
                selected = spec
                selected_reason = "priority"
                break

        if selected is None and current is not None:
            selected = current
            selected_reason = "fallback_current"
        if selected is None and enabled:
            selected = enabled[0]
            selected_reason = "fallback_first_enabled"

        if selected is not None:
            selected_name = str(selected.name)
            if self._active_case_name != selected_name:
                if self._active_case_name:
                    self._case_last_exit[str(self._active_case_name)] = int(generation)
                self._active_case_name = selected_name
                self._active_case_since = int(generation)
        active_specs = [] if selected is None else [selected]

        decision = {
            "generation": int(generation),
            "matched_cases": [str(s.name) for s in matched_sorted],
            "blocked_cases": blocked,
            "active_case": None if selected is None else str(selected.name),
            "active_adapter_group": None if selected is None else str(getattr(selected.adapter, "name", selected.name)),
            "selected_priority": None if selected is None else self._event_case_priority(selected),
            "selected_reason": selected_reason,
            "report_fields": {} if selected is None else self._event_case_report(selected, context),
            "cooldown": {
                "active_since": self._active_case_since,
                "last_exit": dict(self._case_last_exit),
            },
        }
        return active_specs, decision

    def _seed_queue(self) -> None:
        enabled = self._enabled_specs()
        for spec in enabled:
            count = int(max(1, int(self.cfg.bootstrap_events_per_strategy)))
            for _ in range(count):
                self._enqueue_propose(strategy=spec.name, budget=1, source="bootstrap", case=spec.name)

    def _topup_queue(self, enabled: Optional[Sequence[EventStrategySpec]] = None) -> None:
        target = int(max(1, int(self.cfg.target_queue_size)))
        missing = max(0, target - len(self._queue))
        if missing <= 0:
            return

        enabled = list(enabled if enabled is not None else self._enabled_specs())
        if not enabled:
            return
        weights = np.asarray([max(0.0, float(s.weight)) for s in enabled], dtype=float)
        if float(np.sum(weights)) <= 0:
            weights = np.ones(len(enabled), dtype=float)
        probs = weights / float(np.sum(weights))

        for _ in range(missing):
            idx = int(self._rng.choice(len(enabled), p=probs))
            spec = enabled[idx]
            self._enqueue_propose(strategy=spec.name, budget=1, source="topup", case=spec.name)

    def _enqueue_propose(self, *, strategy: str, budget: int, source: str, case: Optional[str] = None) -> None:
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
            "case": str(case if case is not None else strategy),
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

    def _publish_state(self, control: Any) -> None:
        queue_snapshot = [
            {
                "event_id": int(e.get("event_id", -1)),
                "type": str(e.get("type", "")),
                "strategy": str(e.get("strategy", "")),
                "case": str(e.get("case", e.get("strategy", ""))),
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
                "case": str(a.get("case", a.get("strategy", ""))),
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
            "event_decision": dict(self._last_event_decision),
        }
        runtime_summary = {
            "step": self.shared_state["step"],
            "queue_size": self.shared_state["queue_size"],
            "inflight_size": self.shared_state["inflight_size"],
            "archive_size": self.shared_state["archive_size"],
            "event_count": self.shared_state["event_count"],
            "stats": self.shared_state["stats"],
            "event_decision": self.shared_state["event_decision"],
        }
        _ = control
        self._last_runtime_projection = {
            KEY_EVENT_SHARED: runtime_summary,
            KEY_EVENT_QUEUE: queue_snapshot,
            KEY_EVENT_INFLIGHT: inflight_snapshot,
            KEY_EVENT_ARCHIVE: archive_snapshot,
            KEY_EVENT_HISTORY: list(self.event_history),
        }

    def get_runtime_context_projection(self, solver: Any) -> RuntimeContextProjection:
        specs = self._enabled_specs()
        if self._uses_event_cases():
            specs = (
                []
                if self._active_case_name is None
                else [
                    spec
                    for spec in specs
                    if str(spec.name) == str(self._active_case_name)
                ]
            )
        aggregation = aggregate_adapter_runtime_projections(
            solver,
            owner_source=f"adapter.{self.__class__.__name__}",
            own_fields=self._last_runtime_projection,
            children=tuple(
                (
                    f"adapter.event.{spec.name}:{spec.adapter.__class__.__name__}",
                    spec.adapter,
                )
                for spec in specs
            ),
        )
        self._last_projection_writers = dict(aggregation.field_sources)
        return aggregation.projection

    def get_runtime_context_projection_sources(self, solver: Any) -> Dict[str, str]:
        del solver
        return dict(self._last_projection_writers)

    def get_state(self) -> Dict[str, Any]:
        return {
            "step": int(self._step),
            "event_id": int(self._event_id),
            "queue": list(self._queue),
            "inflight": list(self._inflight),
            "archive": list(self.archive),
            "event_history": list(self.event_history),
            "stats": dict(self._stats),
            "active_case_name": self._active_case_name,
            "active_case_since": self._active_case_since,
            "case_last_exit": dict(self._case_last_exit),
            "last_event_decision": dict(self._last_event_decision),
        }

    def set_state(self, state: Dict[str, Any]) -> None:
        self._step = int(state.get("step", 0))
        self._event_id = int(state.get("event_id", 0))
        self._queue = list(state.get("queue", []))
        self._inflight = list(state.get("inflight", []))
        self.archive = list(state.get("archive", []))
        self.event_history = list(state.get("event_history", []))
        self._stats = dict(state.get("stats", {}))
        active = state.get("active_case_name", None)
        self._active_case_name = None if active is None else str(active)
        since = state.get("active_case_since", None)
        self._active_case_since = None if since is None else int(since)
        self._case_last_exit = {str(k): int(v) for k, v in dict(state.get("case_last_exit", {})).items()}
        self._last_event_decision = dict(state.get("last_event_decision", {}))
