# -*- coding: utf-8 -*-
"""Bias-layer configuration for this project (registry only)."""

from __future__ import annotations

from dataclasses import dataclass
from dataclasses import field
from dataclasses import fields
from typing import Any, Callable, Dict, Optional

from nsgablack.bias import BiasModule


@dataclass(frozen=True)
class BiasConfig:
    enable_bias: bool = False


@dataclass(frozen=True)
class BiasSpec:
    key: str
    params: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class BiasRegistry:
    registry: tuple[BiasSpec, ...] = ()


def get_bias_registry() -> BiasRegistry:
    return BiasRegistry(
        registry=(
            BiasSpec(key="none", params={"enable_bias": False}),
            BiasSpec(key="default", params={"enable_bias": True}),
        )
    )


BiasBuilder = Callable[[Dict[str, Any]], object]

_BIAS_BUILDERS: Dict[str, BiasBuilder] = {}


def register_bias_builder(key: str, builder: BiasBuilder) -> None:
    _BIAS_BUILDERS[str(key).strip().lower()] = builder


def _split_config_kwargs(config_cls, params: Dict[str, Any]) -> tuple[object, Dict[str, Any]]:
    if not params:
        return config_cls(), {}
    cfg_fields = {f.name for f in fields(config_cls)}
    cfg_kwargs = {k: v for k, v in params.items() if k in cfg_fields}
    other = {k: v for k, v in params.items() if k not in cfg_fields}
    return config_cls(**cfg_kwargs), other


def _build_with_config(config_cls, params: Dict[str, Any], build_fn: Callable[..., object]) -> object:
    if "config" in params and isinstance(params["config"], config_cls):
        cfg = params["config"]
        return build_fn(cfg=cfg)
    cfg, _ = _split_config_kwargs(config_cls, params)
    return build_fn(cfg=cfg)


def _build_bias_from_spec(spec: BiasSpec) -> object:
    key = str(spec.key).strip().lower()
    builder = _BIAS_BUILDERS.get(key)
    if builder is None:
        raise ValueError(f"Unknown bias key: {spec.key}")
    return builder(dict(spec.params or {}))


def build_bias(registry: BiasRegistry, key: str) -> object:
    lookup = str(key).strip().lower()
    for spec in tuple(registry.registry or ()):
        if str(spec.key).strip().lower() == lookup:
            return _build_bias_from_spec(spec)
    raise ValueError(f"Bias key not registered: {key}")


def _register_builtin_biases() -> None:
    from .example_bias import build_bias_module

    def _default_builder(params: Dict[str, Any]) -> BiasModule:
        return _build_with_config(BiasConfig, params, build_bias_module)

    register_bias_builder("default", _default_builder)
    register_bias_builder("none", _default_builder)


_register_builtin_biases()
