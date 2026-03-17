# -*- coding: utf-8 -*-
"""Pipeline-layer configuration for this project (registry only)."""

from __future__ import annotations

from dataclasses import dataclass
from dataclasses import field
from dataclasses import fields
from typing import Any, Callable, Dict, Optional

from nsgablack.representation import (
    ClipRepair,
    GaussianMutation,
    RepresentationPipeline,
    UniformInitializer,
)


@dataclass(frozen=True)
class PipelineConfig:
    low: float = -5.0
    high: float = 5.0
    mutation_sigma: float = 0.25


@dataclass(frozen=True)
class PipelineSpec:
    key: str
    params: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class PipelineRegistry:
    registry: tuple[PipelineSpec, ...] = ()


def get_pipeline_registry() -> PipelineRegistry:
    return PipelineRegistry(
        registry=(
            PipelineSpec(key="default", params={"low": -5.0, "high": 5.0, "mutation_sigma": 0.25}),
        )
    )


PipelineBuilder = Callable[[Dict[str, Any]], object]

_PIPELINE_BUILDERS: Dict[str, PipelineBuilder] = {}


def register_pipeline_builder(key: str, builder: PipelineBuilder) -> None:
    _PIPELINE_BUILDERS[str(key).strip().lower()] = builder


def _split_config_kwargs(config_cls, params: Dict[str, Any]) -> tuple[object, Dict[str, Any]]:
    if not params:
        return config_cls(), {}
    cfg_fields = {f.name for f in fields(config_cls)}
    cfg_kwargs = {k: v for k, v in params.items() if k in cfg_fields}
    other = {k: v for k, v in params.items() if k not in cfg_fields}
    return config_cls(**cfg_kwargs), other


def _build_pipeline_from_config(cfg: Optional[PipelineConfig] = None) -> RepresentationPipeline:
    cfg = cfg or PipelineConfig()
    pipeline = RepresentationPipeline(
        initializer=UniformInitializer(low=cfg.low, high=cfg.high),
        mutator=GaussianMutation(sigma=cfg.mutation_sigma, low=cfg.low, high=cfg.high),
        repair=ClipRepair(low=cfg.low, high=cfg.high),
        encoder=None,
    )
    pipeline.context_requires = ()
    pipeline.context_provides = ()
    pipeline.context_mutates = ()
    pipeline.context_cache = ()
    pipeline.context_notes = "No context read/write in this minimal pipeline."
    return pipeline


def _build_with_config(config_cls, params: Dict[str, Any], build_fn: Callable[[object], object]) -> object:
    if "config" in params and isinstance(params["config"], config_cls):
        cfg = params["config"]
        return build_fn(cfg)
    cfg, _ = _split_config_kwargs(config_cls, params)
    return build_fn(cfg)


def _build_pipeline_from_spec(spec: PipelineSpec) -> object:
    key = str(spec.key).strip().lower()
    builder = _PIPELINE_BUILDERS.get(key)
    if builder is None:
        raise ValueError(f"Unknown pipeline key: {spec.key}")
    return builder(dict(spec.params or {}))


def build_pipeline(registry: PipelineRegistry, key: str) -> object:
    lookup = str(key).strip().lower()
    for spec in tuple(registry.registry or ()):
        if str(spec.key).strip().lower() == lookup:
            return _build_pipeline_from_spec(spec)
    raise ValueError(f"Pipeline key not registered: {key}")


def _register_builtin_pipelines() -> None:
    def _default_builder(params: Dict[str, Any]) -> RepresentationPipeline:
        return _build_with_config(PipelineConfig, params, _build_pipeline_from_config)

    register_pipeline_builder("default", _default_builder)


_register_builtin_pipelines()
