"""OpenTelemetry tracing plugin for solver/adapter/plugin runtime events."""

from __future__ import annotations

from contextlib import nullcontext
from dataclasses import dataclass
from types import MethodType
from typing import Any, Dict, List, Optional, Tuple
import os
import warnings

from ..base import Plugin


@dataclass
class OpenTelemetryTracingConfig:
    service_name: str = "nsgablack"
    service_version: str = "dev"
    configure_provider: bool = True
    console_export: bool = False
    otlp_http_endpoint: str = ""
    trace_evaluate: bool = True
    trace_adapter: bool = True
    trace_plugin_events: bool = True


class OpenTelemetryTracingPlugin(Plugin):
    context_requires = ("generation",)
    context_provides = ()
    context_mutates = ()
    context_cache = ()
    context_notes = (
        "Emits OpenTelemetry spans for evaluate/adapter/plugin lifecycle to trace performance and failures.",
    )

    def __init__(
        self,
        name: str = "otel_tracing",
        *,
        config: Optional[OpenTelemetryTracingConfig] = None,
        priority: int = 1,
    ) -> None:
        super().__init__(name=name, priority=priority)
        self.cfg = config or OpenTelemetryTracingConfig()
        self._tracer = None
        self._trace_api = None
        self._restore: List[Tuple[Any, str, Any]] = []
        self._span_counter: int = 0
        self._enabled: bool = False

    def on_solver_init(self, solver: Any):
        self._restore = []
        self._span_counter = 0
        self._enabled = False
        self._setup_tracer()
        if self._tracer is None:
            return None
        self._enabled = True

        if bool(self.cfg.trace_evaluate):
            self._wrap_method(
                solver,
                "evaluate_individual",
                span_name="solver.evaluate_individual",
                attrs={"component": "solver", "method": "evaluate_individual"},
            )
            self._wrap_method(
                solver,
                "evaluate_population",
                span_name="solver.evaluate_population",
                attrs={"component": "solver", "method": "evaluate_population"},
            )
        if bool(self.cfg.trace_adapter):
            adapter = getattr(solver, "adapter", None)
            if adapter is not None:
                self._wrap_method(
                    adapter,
                    "propose",
                    span_name="adapter.propose",
                    attrs={"component": "adapter", "method": "propose", "class": adapter.__class__.__name__},
                )
                self._wrap_method(
                    adapter,
                    "update",
                    span_name="adapter.update",
                    attrs={"component": "adapter", "method": "update", "class": adapter.__class__.__name__},
                )
        if bool(self.cfg.trace_plugin_events):
            pm = getattr(solver, "plugin_manager", None)
            if pm is not None:
                self._wrap_method(
                    pm,
                    "trigger",
                    span_name="plugin.trigger",
                    attrs={"component": "plugin_manager", "method": "trigger"},
                    dynamic_event_arg_index=0,
                )
        return None

    def on_solver_finish(self, result: Dict[str, Any]):
        self._restore_wrapped_methods()
        artifacts = result.setdefault("artifacts", {})
        if isinstance(artifacts, dict):
            artifacts["otel_tracing"] = {
                "enabled": bool(self._enabled),
                "spans_emitted": int(self._span_counter),
                "service_name": str(self.cfg.service_name),
                "otlp_http_endpoint": str(self.cfg.otlp_http_endpoint or ""),
                "console_export": bool(self.cfg.console_export),
            }
        return None

    def _setup_tracer(self) -> None:
        try:
            from opentelemetry import trace
        except Exception as exc:
            warnings.warn(f"OpenTelemetry API not available; tracing disabled ({exc!r})")
            return
        self._trace_api = trace

        if bool(self.cfg.configure_provider):
            try:
                from opentelemetry.sdk.resources import Resource
                from opentelemetry.sdk.trace import TracerProvider
                from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter

                provider = TracerProvider(
                    resource=Resource.create(
                        {
                            "service.name": str(self.cfg.service_name),
                            "service.version": str(self.cfg.service_version),
                        }
                    )
                )
                if bool(self.cfg.console_export):
                    provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))
                endpoint = str(self.cfg.otlp_http_endpoint or os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT", "")).strip()
                if endpoint:
                    try:
                        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter

                        provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(endpoint=endpoint)))
                    except Exception as exc:
                        warnings.warn(f"OTLP exporter not available; skip endpoint {endpoint!r} ({exc!r})")
                trace.set_tracer_provider(provider)
            except Exception as exc:
                warnings.warn(f"OpenTelemetry SDK provider setup failed; continue with current provider ({exc!r})")

        self._tracer = trace.get_tracer(str(self.cfg.service_name))

    def _span_context(self, span_name: str, attrs: Dict[str, Any]):
        if self._tracer is None:
            return nullcontext()
        cm = self._tracer.start_as_current_span(span_name)
        # set attributes after enter to avoid SDK differences.
        class _SpanCtx:
            def __enter__(self_nonlocal):
                span = cm.__enter__()
                try:
                    for k, v in (attrs or {}).items():
                        if v is not None:
                            span.set_attribute(str(k), v)
                except Exception:
                    pass
                return span

            def __exit__(self_nonlocal, exc_type, exc, tb):
                return cm.__exit__(exc_type, exc, tb)

        return _SpanCtx()

    def _wrap_method(
        self,
        target: Any,
        method_name: str,
        *,
        span_name: str,
        attrs: Dict[str, Any],
        dynamic_event_arg_index: Optional[int] = None,
    ) -> None:
        original = getattr(target, method_name, None)
        if not callable(original):
            return
        self._restore.append((target, method_name, original))

        def _wrapped(this, *args, **kwargs):
            local_attrs = dict(attrs or {})
            if dynamic_event_arg_index is not None and len(args) > dynamic_event_arg_index:
                local_attrs["event_name"] = str(args[dynamic_event_arg_index])
            with self._span_context(span_name, local_attrs):
                self._span_counter += 1
                return original(*args, **kwargs)

        setattr(target, method_name, MethodType(_wrapped, target))

    def _restore_wrapped_methods(self) -> None:
        for target, method_name, original in reversed(self._restore):
            try:
                setattr(target, method_name, original)
            except Exception:
                continue
        self._restore = []
