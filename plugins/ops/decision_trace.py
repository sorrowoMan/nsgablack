"""Decision trace plugin: deterministic replay of runtime decision paths."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from types import MethodType
from typing import Any, Dict, List, Mapping, Optional, Tuple
import json
import time

from ..base import Plugin
from ...utils.context.context_events import record_context_event
from ...utils.context.context_keys import KEY_CONTEXT_EVENTS, KEY_DECISION_TRACE_REF
from ...utils.engineering.file_io import atomic_write_text
from ...utils.runtime.decision_trace import append_decision_jsonl, build_decision_event


@dataclass
class DecisionTraceConfig:
    output_dir: str = "runs"
    run_id: str = "run"
    overwrite: bool = True
    flush_every: int = 1
    capture_evaluate: bool = True
    capture_adapter: bool = True
    capture_plugin_events: bool = True
    include_context_events: bool = True
    max_context_events_mirror: int = 2000


class DecisionTracePlugin(Plugin):
    context_requires = ("generation",)
    context_provides = ("decision_trace_ref",)
    context_mutates = ("decision_trace_ref",)
    context_cache = ()
    context_notes = (
        "Records deterministic decision events with reason/evidence for replay and audit.",
    )

    def __init__(
        self,
        name: str = "decision_trace",
        *,
        config: Optional[DecisionTraceConfig] = None,
        priority: int = 2,
    ) -> None:
        super().__init__(name=name, priority=priority)
        self.cfg = config or DecisionTraceConfig()
        self._seq: int = 0
        self._events: List[Dict[str, Any]] = []
        self._restore: List[Tuple[Any, str, Any]] = []
        self._jsonl_path: Optional[Path] = None
        self._summary_path: Optional[Path] = None

    def on_solver_init(self, solver: Any):
        self._seq = 0
        self._events = []
        self._restore_wrapped_methods()
        out_dir = Path(str(self.cfg.output_dir)).expanduser().resolve()
        out_dir.mkdir(parents=True, exist_ok=True)
        self._jsonl_path = out_dir / f"{self.cfg.run_id}.decision_trace.jsonl"
        self._summary_path = out_dir / f"{self.cfg.run_id}.decision_trace.summary.json"
        if self._jsonl_path.exists() and not bool(self.cfg.overwrite):
            raise FileExistsError(f"DecisionTracePlugin: file exists: {self._jsonl_path}")
        if bool(self.cfg.overwrite):
            self._jsonl_path.write_text("", encoding="utf-8")

        # expose sink for semantic decisions from any component
        setattr(solver, "_decision_trace_sink", self.record_decision)
        setattr(solver, "record_decision_event", self.record_decision)

        if bool(self.cfg.capture_evaluate):
            self._wrap_method(solver, "evaluate_individual", "solver.evaluate_individual")
            self._wrap_method(solver, "evaluate_population", "solver.evaluate_population")
        if bool(self.cfg.capture_adapter):
            adapter = getattr(solver, "adapter", None)
            if adapter is not None:
                self._wrap_method(adapter, "propose", "adapter.propose")
                self._wrap_method(adapter, "update", "adapter.update")
        if bool(self.cfg.capture_plugin_events):
            pm = getattr(solver, "plugin_manager", None)
            if pm is not None:
                self._wrap_method(pm, "trigger", "plugin.trigger", event_name_arg_index=0)
        return None

    def on_generation_end(self, generation: int):
        # Flush periodically to keep replay robust for long runs.
        if int(self.cfg.flush_every) > 0 and (int(generation) + 1) % int(self.cfg.flush_every) == 0:
            self._flush_summary(final=False)
        return None

    def on_solver_finish(self, result: Dict[str, Any]):
        self._restore_wrapped_methods()
        self._flush_summary(final=True)
        artifacts = result.setdefault("artifacts", {})
        if isinstance(artifacts, dict):
            artifacts["decision_trace_jsonl"] = str(self._jsonl_path) if self._jsonl_path else None
            artifacts["decision_trace_summary"] = str(self._summary_path) if self._summary_path else None
            artifacts["decision_trace_count"] = int(len(self._events))
        return None

    def record_decision(
        self,
        *,
        event_type: str,
        component: str,
        decision: str,
        reason_code: str,
        inputs: Optional[Mapping[str, Any]] = None,
        thresholds: Optional[Mapping[str, Any]] = None,
        evidence: Optional[Mapping[str, Any]] = None,
        outcome: Optional[Mapping[str, Any]] = None,
    ) -> Dict[str, Any]:
        solver = self.solver
        generation = int(getattr(solver, "generation", 0) or 0) if solver is not None else None
        step = int(getattr(solver, "step_count", generation or 0) or 0) if solver is not None else None
        self._seq += 1
        event = build_decision_event(
            seq=self._seq,
            event_type=str(event_type),
            component=str(component),
            decision=str(decision),
            reason_code=str(reason_code),
            generation=generation,
            step=step,
            inputs=inputs,
            thresholds=thresholds,
            evidence=evidence,
            outcome=outcome,
            run_id=str(getattr(self.cfg, "run_id", "run")),
        )
        self._events.append(event)
        if self._jsonl_path is not None:
            append_decision_jsonl(self._jsonl_path, event)
        if bool(self.cfg.include_context_events) and solver is not None:
            ctx = getattr(solver, "context", None)
            if isinstance(ctx, dict):
                if self._jsonl_path is not None:
                    ctx[KEY_DECISION_TRACE_REF] = str(self._jsonl_path)
                    record_context_event(
                        ctx,
                        kind="set",
                        key=KEY_DECISION_TRACE_REF,
                        value=str(self._jsonl_path),
                        source=f"plugin.{self.name}",
                        generation=generation,
                        step=step,
                        events_key=KEY_CONTEXT_EVENTS,
                    )
        return event

    def _wrap_method(
        self,
        target: Any,
        method_name: str,
        component_name: str,
        *,
        event_name_arg_index: Optional[int] = None,
    ) -> None:
        original = getattr(target, method_name, None)
        if not callable(original):
            return
        self._restore.append((target, method_name, original))

        def _wrapped(this, *args, **kwargs):
            start = time.time()
            dynamic_event = None
            if event_name_arg_index is not None and len(args) > event_name_arg_index:
                dynamic_event = str(args[event_name_arg_index])
            try:
                result = original(*args, **kwargs)
                duration_ms = (time.time() - start) * 1000.0
                self.record_decision(
                    event_type="runtime_call",
                    component=component_name,
                    decision="completed",
                    reason_code=dynamic_event or "normal",
                    inputs={"args_len": len(args), "kwargs": sorted(list(kwargs.keys()))},
                    evidence={"duration_ms": duration_ms},
                    outcome={"has_result": result is not None},
                )
                return result
            except Exception as exc:
                duration_ms = (time.time() - start) * 1000.0
                self.record_decision(
                    event_type="runtime_call",
                    component=component_name,
                    decision="failed",
                    reason_code=dynamic_event or "exception",
                    inputs={"args_len": len(args), "kwargs": sorted(list(kwargs.keys()))},
                    evidence={"duration_ms": duration_ms, "exception": exc.__class__.__name__},
                    outcome={"message": str(exc)},
                )
                raise

        setattr(target, method_name, MethodType(_wrapped, target))

    def _restore_wrapped_methods(self) -> None:
        for target, method_name, original in reversed(self._restore):
            try:
                setattr(target, method_name, original)
            except Exception:
                continue
        self._restore = []

    def _flush_summary(self, *, final: bool) -> None:
        if self._summary_path is None:
            return
        by_type: Dict[str, int] = {}
        by_component: Dict[str, int] = {}
        for e in self._events:
            t = str(e.get("event_type", "unknown"))
            c = str(e.get("component", "unknown"))
            by_type[t] = int(by_type.get(t, 0)) + 1
            by_component[c] = int(by_component.get(c, 0)) + 1
        payload = {
            "run_id": str(self.cfg.run_id),
            "final": bool(final),
            "count": int(len(self._events)),
            "first_seq": int(self._events[0]["seq"]) if self._events else None,
            "last_seq": int(self._events[-1]["seq"]) if self._events else None,
            "event_type_counts": by_type,
            "component_counts": by_component,
            "jsonl_path": str(self._jsonl_path) if self._jsonl_path is not None else None,
        }
        atomic_write_text(self._summary_path, json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
