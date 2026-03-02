"""Sequence graph plugin: record unique component interaction orders."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from types import MethodType
from typing import Any, Dict, Optional, Sequence, Tuple
import time

from ..base import Plugin
from ...utils.context.context_keys import KEY_SEQUENCE_GRAPH_REF
from ...utils.engineering.file_io import atomic_write_json
from ...utils.engineering.schema_version import stamp_schema
from ...utils.runtime.sequence_graph import SequenceGraphRecorder, build_sequence_token


@dataclass
class SequenceGraphConfig:
    output_dir: str = "runs"
    run_id: str = "run"
    overwrite: bool = True
    flush_every: int = 1
    boundary_groups: Optional[Sequence[Sequence[str]]] = None
    ignore_patterns: Optional[Sequence[str]] = None
    max_sequence_length: int = 4096
    max_sequences: int = 5000
    capture_adapter: bool = True
    capture_evaluate_population: bool = True
    capture_evaluate_individual: bool = False
    capture_plugin_events: bool = True
    trace_mode: str = "off"
    trace_sample_rate: float = 0.02
    trace_max_events: int = 20000
    trace_seed: Optional[int] = None


class SequenceGraphPlugin(Plugin):
    context_requires = ()
    context_provides = (KEY_SEQUENCE_GRAPH_REF,)
    context_mutates = (KEY_SEQUENCE_GRAPH_REF,)
    context_cache = ()
    context_notes = (
        "Records unique component interaction sequences and writes a compact graph JSON artifact.",
    )

    def __init__(
        self,
        name: str = "sequence_graph",
        *,
        config: Optional[SequenceGraphConfig] = None,
        priority: int = 3,
    ) -> None:
        super().__init__(name=name, priority=priority)
        self.cfg = config or SequenceGraphConfig()
        self._recorder: Optional[SequenceGraphRecorder] = None
        self._graph_path: Optional[Path] = None
        self._restore: list[Tuple[Any, str, Any]] = []
        self._prev_event_hook = None
        self._hooked_pm = None
        self._last_flush_generation: Optional[int] = None

    def on_solver_init(self, solver: Any):
        self._restore_wrapped_methods()
        self._restore_event_hook()
        self._recorder = SequenceGraphRecorder(
            boundary_groups=self.cfg.boundary_groups,
            ignore_patterns=self.cfg.ignore_patterns,
            max_sequence_length=self.cfg.max_sequence_length,
            max_sequences=self.cfg.max_sequences,
            trace_mode=self.cfg.trace_mode,
            trace_sample_rate=self.cfg.trace_sample_rate,
            trace_max_events=self.cfg.trace_max_events,
            trace_seed=self.cfg.trace_seed,
        )
        out_dir = Path(str(self.cfg.output_dir)).expanduser().resolve()
        out_dir.mkdir(parents=True, exist_ok=True)
        self._graph_path = out_dir / f"{self.cfg.run_id}.sequence_graph.json"
        if self._graph_path.exists() and not bool(self.cfg.overwrite):
            raise FileExistsError(f"SequenceGraphPlugin: file exists: {self._graph_path}")

        setattr(solver, "_sequence_graph_sink", self.record_event)
        setattr(solver, "record_sequence_event", self.record_event)

        if bool(self.cfg.capture_plugin_events):
            pm = getattr(solver, "plugin_manager", None)
            if pm is not None and hasattr(pm, "set_event_hook"):
                self._prev_event_hook = getattr(pm, "event_hook", None)

                def _hook(payload: Dict[str, Any]) -> None:
                    if callable(self._prev_event_hook):
                        try:
                            self._prev_event_hook(payload)
                        except Exception:
                            pass
                    self._handle_plugin_event(payload)

                pm.set_event_hook(_hook)
                self._hooked_pm = pm

        if bool(self.cfg.capture_evaluate_population):
            self._wrap_method(
                solver,
                "evaluate_population",
                kind="solver",
                name=solver.__class__.__name__,
                action="evaluate_population",
            )
        if bool(self.cfg.capture_evaluate_individual):
            self._wrap_method(
                solver,
                "evaluate_individual",
                kind="solver",
                name=solver.__class__.__name__,
                action="evaluate_individual",
            )

        if bool(self.cfg.capture_adapter):
            adapter = getattr(solver, "adapter", None)
            if adapter is not None:
                adapter_name = getattr(adapter, "name", None) or adapter.__class__.__name__
                self._wrap_method(adapter, "propose", kind="adapter", name=adapter_name, action="propose")
                self._wrap_method(adapter, "update", kind="adapter", name=adapter_name, action="update")
        return None

    def on_generation_end(self, generation: int):
        if int(self.cfg.flush_every) <= 0:
            return None
        if (int(generation) + 1) % int(self.cfg.flush_every) != 0:
            return None
        if self._last_flush_generation == int(generation):
            return None
        self._flush(final=False)
        self._last_flush_generation = int(generation)
        return None

    def on_solver_finish(self, result: Dict[str, Any]):
        self._restore_wrapped_methods()
        self._restore_event_hook()
        if self._recorder is not None:
            self._recorder.finalize_cycle()
        self._flush(final=True)
        artifacts = result.setdefault("artifacts", {})
        if isinstance(artifacts, dict):
            artifacts["sequence_graph_json"] = str(self._graph_path) if self._graph_path is not None else None
        return None

    def on_context_build(self, ctx: Dict[str, Any]) -> Dict[str, Any]:
        if self._graph_path is not None:
            ctx[KEY_SEQUENCE_GRAPH_REF] = str(self._graph_path)
        return ctx

    def record_event(
        self,
        *,
        token: str,
        generation: Optional[int] = None,
        step: Optional[int] = None,
        capture_trace: bool = True,
        trace_meta: Optional[Dict[str, Any]] = None,
    ) -> Optional[str]:
        if self._recorder is None:
            return None
        gen = generation
        step_val = step
        solver = self.solver
        if gen is None and solver is not None:
            gen = getattr(solver, "generation", None)
        if step_val is None and solver is not None:
            step_val = getattr(solver, "step_count", None)
        try:
            self._recorder.record_event(
                str(token),
                generation=gen,
                step=step_val,
                capture_trace=bool(capture_trace),
                trace_meta=trace_meta if isinstance(trace_meta, dict) else None,
            )
        except Exception:
            return None
        return str(token)

    def _trace_start(
        self,
        *,
        token: str,
        generation: Optional[int] = None,
        step: Optional[int] = None,
    ) -> Optional[Dict[str, Any]]:
        if self._recorder is None:
            return None
        gen = generation
        step_val = step
        solver = self.solver
        if gen is None and solver is not None:
            gen = getattr(solver, "generation", None)
        if step_val is None and solver is not None:
            step_val = getattr(solver, "step_count", None)
        try:
            return self._recorder.start_trace_span(
                str(token),
                generation=gen,
                step=step_val,
            )
        except Exception:
            return None

    def _trace_end(
        self,
        handle: Optional[Dict[str, Any]],
        *,
        status: str = "ok",
        error_type: Optional[str] = None,
        trace_meta: Optional[Dict[str, Any]] = None,
    ) -> None:
        if self._recorder is None:
            return
        try:
            self._recorder.end_trace_span(
                handle,
                status=status,
                error_type=error_type,
                meta=trace_meta if isinstance(trace_meta, dict) else None,
            )
        except Exception:
            return

    def _handle_plugin_event(self, payload: Dict[str, Any]) -> None:
        if self._recorder is None:
            return
        plugin_name = str(payload.get("plugin_name", "") or "")
        if plugin_name == self.name:
            return
        event_name = str(payload.get("event_name", "") or "")
        if not event_name:
            return
        token = build_sequence_token("plugin", plugin_name, event_name)
        self.record_event(
            token=token,
            capture_trace=True,
            trace_meta={
                "plugin_event_mode": payload.get("mode"),
                "plugin_event_name": event_name,
                "plugin_event_status": payload.get("status"),
                "plugin_event_name_raw": payload.get("event_name"),
            },
        )

    def _wrap_method(self, target: Any, method_name: str, *, kind: str, name: str, action: str) -> None:
        original = getattr(target, method_name, None)
        if not callable(original):
            return
        self._restore.append((target, method_name, original))
        token = build_sequence_token(kind, name, action)

        def _wrapped(this, *args, **kwargs):
            self.record_event(token=token, capture_trace=False)
            span = self._trace_start(token=token)
            try:
                out = original(*args, **kwargs)
            except Exception as exc:
                self._trace_end(
                    span,
                    status="error",
                    error_type=exc.__class__.__name__,
                )
                raise
            self._trace_end(span, status="ok")
            return out

        setattr(target, method_name, MethodType(_wrapped, target))

    def _restore_wrapped_methods(self) -> None:
        for target, method_name, original in reversed(self._restore):
            try:
                setattr(target, method_name, original)
            except Exception:
                continue
        self._restore = []

    def _restore_event_hook(self) -> None:
        if self._hooked_pm is not None:
            try:
                self._hooked_pm.set_event_hook(self._prev_event_hook)
            except Exception:
                pass
        self._hooked_pm = None
        self._prev_event_hook = None

    def _flush(self, *, final: bool) -> None:
        if self._graph_path is None or self._recorder is None:
            return
        payload = self._recorder.snapshot()
        payload.update(
            {
                "run_id": str(self.cfg.run_id),
                "final": bool(final),
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                "output_path": str(self._graph_path),
            }
        )
        payload = stamp_schema(payload, "sequence_graph")
        atomic_write_json(self._graph_path, payload, ensure_ascii=False, indent=2, encoding="utf-8")
