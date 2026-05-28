# -*- coding: utf-8 -*-
# Plugin-layer configuration for this project (registries only).

from __future__ import annotations

from dataclasses import dataclass
from dataclasses import field
from dataclasses import fields
from typing import Any, Callable, Dict, Sequence

from .example_plugin import ExampleProjectPlugin


@dataclass(frozen=True)
class PluginSpec:
    key: str
    params: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class GovernancePluginRegistry:
    registry: tuple[PluginSpec, ...] = ()


@dataclass(frozen=True)
class OpsPluginRegistry:
    registry: tuple[PluginSpec, ...] = ()


def get_governance_plugin_registry() -> GovernancePluginRegistry:
    return GovernancePluginRegistry(registry=())


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


def _build_simple(plugin_cls, params: Dict[str, Any]):
    return plugin_cls(**(params or {}))


def _build_example_plugin(params: Dict[str, Any]) -> object:
    return _build_simple(ExampleProjectPlugin, params)


_GOVERNANCE_PLUGIN_BUILDERS: Dict[str, PluginBuilder] = {}
_OPS_PLUGIN_BUILDERS: Dict[str, PluginBuilder] = {
    "example_plugin": _build_example_plugin,
}


def register_governance_plugin_builder(key: str, builder: PluginBuilder) -> None:
    _GOVERNANCE_PLUGIN_BUILDERS[str(key).strip().lower()] = builder


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


def build_governance_plugins(registry: GovernancePluginRegistry, keys: Sequence[str]) -> list[object]:
    plugins: list[object] = []
    for key in keys:
        spec = _find_spec(registry.registry, key)
        plugins.append(_build_plugin_from_spec(spec, _GOVERNANCE_PLUGIN_BUILDERS))
    return plugins


def build_ops_plugins(registry: OpsPluginRegistry, keys: Sequence[str]) -> list[object]:
    plugins: list[object] = []
    for key in keys:
        spec = _find_spec(registry.registry, key)
        plugins.append(_build_plugin_from_spec(spec, _OPS_PLUGIN_BUILDERS))
    return plugins


def attach_governance_plugins(solver, registry, keys: Sequence[str]) -> None:
    plugins = build_governance_plugins(registry, keys)
    for plugin in plugins:
        solver.add_plugin(plugin)


def attach_ops_plugins(solver, registry, keys: Sequence[str]) -> None:
    plugins = build_ops_plugins(registry, keys)
    for plugin in plugins:
        solver.add_plugin(plugin)


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
