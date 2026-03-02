"""Sequence graph recorder and helpers."""

from __future__ import annotations

import asyncio
from contextvars import ContextVar
from dataclasses import dataclass, field
import fnmatch
import hashlib
import random
import threading
import time
from typing import Any, Dict, Iterable, List, Optional, Sequence


def _clean_token_part(value: Any, *, fallback: str) -> str:
    text = str(value or "").strip()
    if not text:
        return fallback
    return text.replace(" ", "_").replace(".", "_")


def build_sequence_token(kind: str, name: str, action: str) -> str:
    """Build a stable event token for sequence graphs."""
    return ".".join(
        [
            _clean_token_part(kind, fallback="event"),
            _clean_token_part(name, fallback="unknown"),
            _clean_token_part(action, fallback="action"),
        ]
    )


def _runtime_ids() -> tuple[int, Optional[str]]:
    """Return lightweight runtime ids for trace events."""
    thread_id = int(threading.get_ident())
    task_id: Optional[str] = None
    try:
        task = asyncio.current_task()
    except Exception:
        task = None
    if task is not None:
        try:
            task_name = task.get_name()
        except Exception:
            task_name = None
        task_id = str(task_name) if task_name else f"task:{id(task)}"
    return thread_id, task_id


def record_sequence_event(
    solver: Any,
    *,
    token: str,
    generation: Optional[int] = None,
    step: Optional[int] = None,
) -> Optional[str]:
    """Record a sequence event via plugin sink when available."""
    sink = getattr(solver, "_sequence_graph_sink", None)
    if callable(sink):
        try:
            return sink(token=str(token), generation=generation, step=step)
        except Exception:
            return None
    return None


@dataclass
class SequenceRecord:
    signature: str
    count: int
    length: int
    events: List[str] = field(default_factory=list)
    truncated: bool = False
    first_cycle: int = 0
    last_cycle: int = 0
    first_generation: Optional[int] = None
    last_generation: Optional[int] = None
    first_step: Optional[int] = None
    last_step: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "signature": self.signature,
            "count": int(self.count),
            "length": int(self.length),
            "events": list(self.events),
            "truncated": bool(self.truncated),
            "first_cycle": int(self.first_cycle),
            "last_cycle": int(self.last_cycle),
            "first_generation": self.first_generation,
            "last_generation": self.last_generation,
            "first_step": self.first_step,
            "last_step": self.last_step,
        }


class SequenceGraphRecorder:
    """Incremental recorder for unique interaction sequences."""

    def __init__(
        self,
        *,
        boundary_groups: Optional[Sequence[Sequence[str]]] = None,
        ignore_patterns: Optional[Sequence[str]] = None,
        max_sequence_length: int = 4096,
        max_sequences: int = 5000,
        trace_mode: str = "off",
        trace_sample_rate: float = 0.02,
        trace_max_events: int = 20000,
        trace_seed: Optional[int] = None,
    ) -> None:
        self.boundary_groups: List[List[str]] = [
            [str(p) for p in group if str(p).strip()]
            for group in (boundary_groups or [])
            if group
        ]
        if not self.boundary_groups:
            self.boundary_groups = [["adapter.*.propose"], ["solver.*.evaluate_population"]]
        self.ignore_patterns = [str(p) for p in (ignore_patterns or []) if str(p).strip()]
        self.max_sequence_length = max(1, int(max_sequence_length))
        self.max_sequences = max(1, int(max_sequences))

        mode = str(trace_mode or "off").strip().lower()
        if mode not in {"off", "sample", "full"}:
            mode = "off"
        self.trace_mode = mode
        self.trace_sample_rate = min(1.0, max(0.0, float(trace_sample_rate)))
        self.trace_max_events = max(1, int(trace_max_events))
        self.trace_seed = trace_seed
        self._trace_rng = random.Random(trace_seed) if self.trace_mode == "sample" else None
        self._trace_enabled = self.trace_mode != "off"
        self._trace_cycle_decided = False
        self._trace_cycle_enabled = self.trace_mode == "full"
        self._trace_stack: ContextVar[tuple[str, ...]] = ContextVar(
            "sequence_graph_trace_stack",
            default=(),
        )
        self._trace_events: List[Dict[str, Any]] = []
        self._trace_dropped_events = 0
        self._trace_next_span = 1

        self._active_group_index: Optional[int] = None
        self._records: Dict[str, SequenceRecord] = {}
        self._event_counts: Dict[str, int] = {}

        self._current_events: List[str] = []
        self._current_hash = hashlib.sha1()
        self._current_length = 0
        self._current_truncated = False
        self._current_first_generation: Optional[int] = None
        self._current_last_generation: Optional[int] = None
        self._current_first_step: Optional[int] = None
        self._current_last_step: Optional[int] = None

        self.cycle_count = 0
        self.total_events = 0
        self.dropped_sequences = 0

    def _matches_any(self, token: str, patterns: Iterable[str]) -> bool:
        return any(fnmatch.fnmatchcase(token, pat) for pat in patterns)

    def _should_ignore(self, token: str) -> bool:
        if not self.ignore_patterns:
            return False
        return self._matches_any(token, self.ignore_patterns)

    def _is_boundary(self, token: str) -> bool:
        if self._active_group_index is not None:
            group = self.boundary_groups[self._active_group_index]
            return self._matches_any(token, group)
        for idx, group in enumerate(self.boundary_groups):
            if self._matches_any(token, group):
                self._active_group_index = idx
                return True
        return False

    def _reset_current(self) -> None:
        self._current_events = []
        self._current_hash = hashlib.sha1()
        self._current_length = 0
        self._current_truncated = False
        self._current_first_generation = None
        self._current_last_generation = None
        self._current_first_step = None
        self._current_last_step = None
        self._trace_cycle_decided = False
        self._trace_cycle_enabled = self.trace_mode == "full"

    def _ensure_trace_cycle_decision(self) -> None:
        if not self._trace_enabled:
            return
        if self._trace_cycle_decided:
            return
        self._trace_cycle_decided = True
        if self.trace_mode == "full":
            self._trace_cycle_enabled = True
            return
        if self.trace_mode == "sample":
            rng = self._trace_rng
            if rng is None:
                self._trace_cycle_enabled = False
            else:
                self._trace_cycle_enabled = bool(rng.random() <= self.trace_sample_rate)
            return
        self._trace_cycle_enabled = False

    def _new_span_id(self) -> str:
        span_id = f"s{self._trace_next_span}"
        self._trace_next_span += 1
        return span_id

    def _append_trace_event(self, event: Dict[str, Any]) -> None:
        if len(self._trace_events) >= self.trace_max_events:
            self._trace_dropped_events += 1
            return
        self._trace_events.append(event)

    def _trace_event_payload(
        self,
        *,
        token: str,
        generation: Optional[int],
        step: Optional[int],
        start_ns: int,
        end_ns: int,
        span_id: str,
        parent_span_id: Optional[str],
        status: str = "ok",
        error_type: Optional[str] = None,
        trace_type: str = "instant",
        meta: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        thread_id, task_id = _runtime_ids()
        payload: Dict[str, Any] = {
            "token": str(token),
            "generation": int(generation) if generation is not None else None,
            "step": int(step) if step is not None else None,
            "start_ns": int(start_ns),
            "end_ns": int(end_ns),
            "duration_ns": max(0, int(end_ns) - int(start_ns)),
            "thread_id": int(thread_id),
            "task_id": task_id,
            "span_id": str(span_id),
            "parent_span_id": str(parent_span_id) if parent_span_id else None,
            "status": str(status or "ok"),
            "error_type": str(error_type) if error_type else None,
            "trace_type": str(trace_type or "instant"),
        }
        if isinstance(meta, dict) and meta:
            for key, value in meta.items():
                if value is None:
                    continue
                payload[str(key)] = value
        return payload

    def record_instant_trace(
        self,
        token: str,
        *,
        generation: Optional[int] = None,
        step: Optional[int] = None,
        status: str = "ok",
        error_type: Optional[str] = None,
        meta: Optional[Dict[str, Any]] = None,
    ) -> None:
        if not self._trace_enabled:
            return
        self._ensure_trace_cycle_decision()
        if not self._trace_cycle_enabled:
            return
        now_ns = time.perf_counter_ns()
        stack = self._trace_stack.get()
        parent = stack[-1] if stack else None
        span_id = self._new_span_id()
        event = self._trace_event_payload(
            token=str(token),
            generation=generation,
            step=step,
            start_ns=now_ns,
            end_ns=now_ns,
            span_id=span_id,
            parent_span_id=parent,
            status=status,
            error_type=error_type,
            trace_type="instant",
            meta=meta,
        )
        self._append_trace_event(event)

    def start_trace_span(
        self,
        token: str,
        *,
        generation: Optional[int] = None,
        step: Optional[int] = None,
    ) -> Optional[Dict[str, Any]]:
        if not self._trace_enabled:
            return None
        self._ensure_trace_cycle_decision()
        if not self._trace_cycle_enabled:
            return None
        stack = self._trace_stack.get()
        parent = stack[-1] if stack else None
        span_id = self._new_span_id()
        ctx_token = self._trace_stack.set(stack + (span_id,))
        return {
            "token": str(token),
            "generation": int(generation) if generation is not None else None,
            "step": int(step) if step is not None else None,
            "start_ns": int(time.perf_counter_ns()),
            "span_id": span_id,
            "parent_span_id": parent,
            "ctx_token": ctx_token,
        }

    def end_trace_span(
        self,
        handle: Optional[Dict[str, Any]],
        *,
        status: str = "ok",
        error_type: Optional[str] = None,
        meta: Optional[Dict[str, Any]] = None,
    ) -> None:
        if not isinstance(handle, dict):
            return
        ctx_token = handle.get("ctx_token")
        if ctx_token is not None:
            try:
                self._trace_stack.reset(ctx_token)
            except Exception:
                pass
        end_ns = int(time.perf_counter_ns())
        start_ns = int(handle.get("start_ns", end_ns) or end_ns)
        event = self._trace_event_payload(
            token=str(handle.get("token", "")),
            generation=handle.get("generation"),
            step=handle.get("step"),
            start_ns=start_ns,
            end_ns=end_ns,
            span_id=str(handle.get("span_id", self._new_span_id())),
            parent_span_id=(
                str(handle.get("parent_span_id"))
                if handle.get("parent_span_id")
                else None
            ),
            status=status,
            error_type=error_type,
            trace_type="span",
            meta=meta,
        )
        self._append_trace_event(event)

    def _current_signature(self) -> str:
        digest = self._current_hash.hexdigest()
        return f"{self._current_length}:{digest}"

    def record_event(
        self,
        token: str,
        *,
        generation: Optional[int] = None,
        step: Optional[int] = None,
        capture_trace: bool = True,
        trace_meta: Optional[Dict[str, Any]] = None,
    ) -> None:
        text = str(token or "").strip()
        if not text:
            return
        if self._should_ignore(text):
            return
        if self._is_boundary(text) and self._current_length > 0:
            self.finalize_cycle()
        if self._current_length == 0:
            self._ensure_trace_cycle_decision()
            if generation is not None:
                self._current_first_generation = int(generation)
            if step is not None:
                self._current_first_step = int(step)
        else:
            self._ensure_trace_cycle_decision()

        self._current_hash.update(text.encode("utf-8"))
        self._current_hash.update(b"\n")
        self._current_length += 1
        self.total_events += 1
        self._event_counts[text] = int(self._event_counts.get(text, 0)) + 1

        if self._current_length <= self.max_sequence_length:
            self._current_events.append(text)
        else:
            self._current_truncated = True

        if generation is not None:
            self._current_last_generation = int(generation)
        if step is not None:
            self._current_last_step = int(step)
        if bool(capture_trace):
            self.record_instant_trace(
                text,
                generation=generation,
                step=step,
                meta=trace_meta,
            )

    def finalize_cycle(self) -> None:
        if self._current_length <= 0:
            return
        signature = self._current_signature()
        record = self._records.get(signature)
        if record is None and len(self._records) >= self.max_sequences:
            self.dropped_sequences += 1
            self._reset_current()
            return

        if record is None:
            record = SequenceRecord(
                signature=signature,
                count=1,
                length=int(self._current_length),
                events=list(self._current_events),
                truncated=bool(self._current_truncated),
                first_cycle=int(self.cycle_count + 1),
                last_cycle=int(self.cycle_count + 1),
                first_generation=self._current_first_generation,
                last_generation=self._current_last_generation,
                first_step=self._current_first_step,
                last_step=self._current_last_step,
            )
            self._records[signature] = record
        else:
            record.count += 1
            record.last_cycle = int(self.cycle_count + 1)
            if self._current_last_generation is not None:
                record.last_generation = self._current_last_generation
            if self._current_last_step is not None:
                record.last_step = self._current_last_step
        self.cycle_count += 1
        self._reset_current()

    def snapshot(self) -> Dict[str, Any]:
        records = [r.to_dict() for r in self._records.values()]
        records.sort(key=lambda r: (-int(r.get("count", 0)), str(r.get("signature", ""))))
        trace_events = list(self._trace_events)
        trace_events.sort(
            key=lambda e: (
                int(e.get("start_ns", 0) or 0),
                str(e.get("span_id", "")),
            )
        )
        return {
            "cycle_count": int(self.cycle_count),
            "unique_sequences": int(len(self._records)),
            "total_events": int(self.total_events),
            "dropped_sequences": int(self.dropped_sequences),
            "boundary_groups": [list(group) for group in self.boundary_groups],
            "active_boundary_group": self._active_group_index,
            "sequence_records": records,
            "event_counts": dict(self._event_counts),
            "trace_mode": self.trace_mode,
            "trace_sample_rate": float(self.trace_sample_rate),
            "trace_max_events": int(self.trace_max_events),
            "trace_seed": self.trace_seed,
            "trace_event_count": int(len(trace_events)),
            "trace_dropped_events": int(self._trace_dropped_events),
            "trace_events": trace_events,
        }
