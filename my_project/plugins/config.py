# -*- coding: utf-8 -*-
"""Plugin-layer configuration for this project (registries only)."""

from __future__ import annotations

from dataclasses import dataclass
from dataclasses import field
from dataclasses import fields
from typing import Any, Callable, Dict, Sequence

from nsgablack.plugins import (
    AsyncEventHubConfig,
    AsyncEventHubPlugin,
    BasicElitePlugin,
    BenchmarkHarnessConfig,
    BenchmarkHarnessPlugin,
    BoundaryGuardConfig,
    BoundaryGuardPlugin,
    DecisionTraceConfig,
    DecisionTracePlugin,
    DiversityInitPlugin,
    DynamicSwitchPlugin,
    HistoricalElitePlugin,
    MemoryPlugin,
    ModuleReportConfig,
    ModuleReportPlugin,
    MySQLRunLoggerConfig,
    MySQLRunLoggerPlugin,
    OpenTelemetryTracingConfig,
    OpenTelemetryTracingPlugin,
    ParetoArchiveConfig,
    ParetoArchivePlugin,
    ProfilerConfig,
    ProfilerPlugin,
    SensitivityAnalysisConfig,
    SensitivityAnalysisPlugin,
    SequenceGraphConfig,
    SequenceGraphPlugin,
)


@dataclass(frozen=True)
class PluginSpec:
    key: str
    params: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class FlowPluginRegistry:
    registry: tuple[PluginSpec, ...] = ()


@dataclass(frozen=True)
class OpsPluginRegistry:
    registry: tuple[PluginSpec, ...] = ()


def get_flow_plugin_registry() -> FlowPluginRegistry:
    return FlowPluginRegistry(registry=())


def get_ops_plugin_registry() -> OpsPluginRegistry:
    return OpsPluginRegistry(
        registry=(
            PluginSpec(key="example_plugin", params={"interval": 5, "verbose": True}),
        )
    )


PluginBuilder = Callable[[Dict[str, Any]], object]


def _split_config_kwargs(config_cls, params: Dict[str, Any]) -> tuple[object, Dict[str, Any]]:
    if not params:
        return config_cls(), {}
    cfg_fields = {f.name for f in fields(config_cls)}
    cfg_kwargs = {k: v for k, v in params.items() if k in cfg_fields}
    other = {k: v for k, v in params.items() if k not in cfg_fields}
    return config_cls(**cfg_kwargs), other


def _build_with_config(plugin_cls, config_cls, params: Dict[str, Any], *, config_param: str = "config"):
    if "config" in params and isinstance(params["config"], config_cls):
        cfg = params["config"]
        other = {k: v for k, v in params.items() if k != "config"}
        return plugin_cls(**{config_param: cfg}, **other)
    cfg, other = _split_config_kwargs(config_cls, params)
    return plugin_cls(**{config_param: cfg}, **other)


def _build_simple(plugin_cls, params: Dict[str, Any]):
    return plugin_cls(**(params or {}))


def _build_example_plugin(params: Dict[str, Any]) -> object:
    from plugins.example_plugin import ExampleProjectPlugin

    return _build_simple(ExampleProjectPlugin, params)


_FLOW_PLUGIN_BUILDERS: Dict[str, PluginBuilder] = {
    "dynamic_switch": lambda p: _build_simple(DynamicSwitchPlugin, p),
    "basic_elite": lambda p: _build_simple(BasicElitePlugin, p),
    "historical_elite": lambda p: _build_simple(HistoricalElitePlugin, p),
    "pareto_archive": lambda p: _build_with_config(ParetoArchivePlugin, ParetoArchiveConfig, p),
    "diversity_init": lambda p: _build_simple(DiversityInitPlugin, p),
}

_OPS_PLUGIN_BUILDERS: Dict[str, PluginBuilder] = {
    "example_plugin": _build_example_plugin,
    "async_event_hub": lambda p: _build_with_config(
        AsyncEventHubPlugin, AsyncEventHubConfig, p, config_param="cfg"
    ),
    "boundary_guard": lambda p: _build_with_config(
        BoundaryGuardPlugin, BoundaryGuardConfig, p, config_param="cfg"
    ),
    "memory_optimize": lambda p: _build_simple(MemoryPlugin, p),
    "profiler": lambda p: _build_with_config(ProfilerPlugin, ProfilerConfig, p),
    "decision_trace": lambda p: _build_with_config(DecisionTracePlugin, DecisionTraceConfig, p),
    "otel_tracing": lambda p: _build_with_config(
        OpenTelemetryTracingPlugin, OpenTelemetryTracingConfig, p
    ),
    "module_report": lambda p: _build_with_config(ModuleReportPlugin, ModuleReportConfig, p),
    "benchmark_harness": lambda p: _build_with_config(BenchmarkHarnessPlugin, BenchmarkHarnessConfig, p),
    "sensitivity_analysis": lambda p: _build_with_config(
        SensitivityAnalysisPlugin, SensitivityAnalysisConfig, p
    ),
    "sequence_graph": lambda p: _build_with_config(SequenceGraphPlugin, SequenceGraphConfig, p),
    "mysql_run_logger": lambda p: _build_with_config(MySQLRunLoggerPlugin, MySQLRunLoggerConfig, p),
}


def register_flow_plugin_builder(key: str, builder: PluginBuilder) -> None:
    _FLOW_PLUGIN_BUILDERS[str(key).strip().lower()] = builder


def register_ops_plugin_builder(key: str, builder: PluginBuilder) -> None:
    _OPS_PLUGIN_BUILDERS[str(key).strip().lower()] = builder


def _find_spec(registry: Sequence[PluginSpec], key: str) -> PluginSpec:
    lookup = str(key).strip().lower()
    for spec in tuple(registry or ()):
        if str(spec.key).strip().lower() == lookup:
            return spec
    raise ValueError(f"Plugin key not registered: {key}")


def _build_plugin_from_spec(spec: PluginSpec, builders: Dict[str, PluginBuilder]) -> object:
    key = str(spec.key).strip().lower()
    builder = builders.get(key)
    if builder is None:
        raise ValueError(f"Unknown plugin key: {spec.key}")
    params = dict(spec.params or {})
    return builder(params)


def build_flow_plugins(registry: FlowPluginRegistry, keys: Sequence[str]) -> list[object]:
    plugins: list[object] = []
    for key in keys:
        spec = _find_spec(registry.registry, key)
        plugins.append(_build_plugin_from_spec(spec, _FLOW_PLUGIN_BUILDERS))
    return plugins


def build_ops_plugins(registry: OpsPluginRegistry, keys: Sequence[str]) -> list[object]:
    plugins: list[object] = []
    for key in keys:
        spec = _find_spec(registry.registry, key)
        plugins.append(_build_plugin_from_spec(spec, _OPS_PLUGIN_BUILDERS))
    return plugins


# --- Observability + checkpoint registries ---------------------------------
@dataclass(frozen=True)
class ObservabilitySpec:
    key: str
    params: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ObservabilityRegistry:
    registry: tuple[ObservabilitySpec, ...] = ()


def get_observability_registry() -> ObservabilityRegistry:
    return ObservabilityRegistry(
        registry=(
            ObservabilitySpec(
                key="default",
                params={
                    "profile": "default",
                    "enable_profiler": None,
                    "enable_decision_trace": None,
                    "run_dir": "runs",
                },
            ),
            ObservabilitySpec(
                key="quickstart",
                params={
                    "profile": "quickstart",
                    "enable_profiler": None,
                    "enable_decision_trace": None,
                    "run_dir": "runs",
                },
            ),
            ObservabilitySpec(
                key="strict",
                params={
                    "profile": "strict",
                    "enable_profiler": None,
                    "enable_decision_trace": None,
                    "run_dir": "runs",
                },
            ),
        )
    )


@dataclass(frozen=True)
class CheckpointSpec:
    key: str
    params: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class CheckpointRegistry:
    registry: tuple[CheckpointSpec, ...] = ()


def get_checkpoint_registry() -> CheckpointRegistry:
    return CheckpointRegistry(
        registry=(
            CheckpointSpec(
                key="default",
                params={
                    "checkpoint_dir": "runs/checkpoints",
                    "auto_resume": True,
                    "strict": True,
                    "trust_checkpoint": False,
                },
            ),
        )
    )


def get_observability_spec(registry: ObservabilityRegistry, key: str) -> ObservabilitySpec:
    lookup = str(key).strip().lower()
    for spec in tuple(registry.registry or ()):
        if str(spec.key).strip().lower() == lookup:
            return spec
    raise ValueError(f"Observability key not registered: {key}")


def get_checkpoint_spec(registry: CheckpointRegistry, key: str) -> CheckpointSpec:
    lookup = str(key).strip().lower()
    for spec in tuple(registry.registry or ()):
        if str(spec.key).strip().lower() == lookup:
            return spec
    raise ValueError(f"Checkpoint key not registered: {key}")


def apply_observability_profile(solver, registry: ObservabilityRegistry, key: str, run_id: str) -> None:
    from nsgablack.utils.wiring import attach_observability_profile

    spec = get_observability_spec(registry, key)
    obs = spec.params
    attach_observability_profile(
        solver,
        profile=str(obs.get("profile", "default")),
        output_dir=str(obs.get("run_dir", "runs")),
        run_id=run_id,
        enable_profiler=obs.get("enable_profiler", None),
        enable_decision_trace=obs.get("enable_decision_trace", None),
    )
