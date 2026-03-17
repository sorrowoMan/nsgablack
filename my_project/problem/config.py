# -*- coding: utf-8 -*-
"""Problem-layer configuration for this project (registry only)."""

from __future__ import annotations

from dataclasses import dataclass
from dataclasses import field
from dataclasses import fields
from typing import Any, Callable, Dict, Optional

from .example_problem import ExampleProblem

@dataclass(frozen=True)
class ProblemConfig:
    dimension: int = 8


@dataclass(frozen=True)
class ProblemSpec:
    key: str
    params: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ProblemRegistry:
    registry: tuple[ProblemSpec, ...] = ()


def get_problem_registry() -> ProblemRegistry:
    return ProblemRegistry(
        registry=(
            ProblemSpec(key="example", params={"dimension": 8}),
        )
    )


ProblemBuilder = Callable[[Dict[str, Any]], object]

_PROBLEM_BUILDERS: Dict[str, ProblemBuilder] = {}


def register_problem_builder(key: str, builder: ProblemBuilder) -> None:
    _PROBLEM_BUILDERS[str(key).strip().lower()] = builder


def _split_config_kwargs(config_cls, params: Dict[str, Any]) -> tuple[object, Dict[str, Any]]:
    if not params:
        return config_cls(), {}
    cfg_fields = {f.name for f in fields(config_cls)}
    cfg_kwargs = {k: v for k, v in params.items() if k in cfg_fields}
    other = {k: v for k, v in params.items() if k not in cfg_fields}
    return config_cls(**cfg_kwargs), other


def _build_example_problem(cfg: Optional[ProblemConfig] = None) -> ExampleProblem:
    cfg = cfg or ProblemConfig()
    # ExampleProblem currently only needs dimension; bounds/objectives live inside the class.
    return ExampleProblem(dimension=int(cfg.dimension))


def _build_with_config(config_cls, params: Dict[str, Any], build_fn: Callable[[object], object]) -> object:
    if "config" in params and isinstance(params["config"], config_cls):
        cfg = params["config"]
        return build_fn(cfg)
    cfg, _ = _split_config_kwargs(config_cls, params)
    return build_fn(cfg)


def _build_problem_from_spec(spec: ProblemSpec) -> object:
    key = str(spec.key).strip().lower()
    builder = _PROBLEM_BUILDERS.get(key)
    if builder is None:
        raise ValueError(f"Unknown problem key: {spec.key}")
    return builder(dict(spec.params or {}))


def build_problem(registry: ProblemRegistry, key: str) -> object:
    lookup = str(key).strip().lower()
    for spec in tuple(registry.registry or ()):
        if str(spec.key).strip().lower() == lookup:
            return _build_problem_from_spec(spec)
    raise ValueError(f"Problem key not registered: {key}")


def _register_builtin_problems() -> None:
    def _example_builder(params: Dict[str, Any]) -> ExampleProblem:
        return _build_with_config(ProblemConfig, params, _build_example_problem)

    register_problem_builder("example", _example_builder)


_register_builtin_problems()
