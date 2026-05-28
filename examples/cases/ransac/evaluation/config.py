# -*- coding: utf-8 -*-
# L4 evaluation runtime configuration (provider registry only).

from __future__ import annotations

from dataclasses import dataclass
from dataclasses import field
from typing import Any, Callable, Dict, Sequence


@dataclass(frozen=True)
class EvaluationSpec:
    key: str
    params: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class EvaluationRegistry:
    registry: tuple[EvaluationSpec, ...] = ()


def get_evaluation_registry() -> EvaluationRegistry:
    return EvaluationRegistry(registry=())


ProviderBuilder = Callable[[Dict[str, Any]], object]

_EVAL_PROVIDER_BUILDERS: Dict[str, ProviderBuilder] = {}


def register_evaluation_provider_builder(key: str, builder: ProviderBuilder) -> None:
    _EVAL_PROVIDER_BUILDERS[str(key).strip().lower()] = builder


def _find_spec(registry: EvaluationRegistry, key: str) -> EvaluationSpec:
    lookup = str(key).strip().lower()
    for spec in tuple(registry.registry or ()):
        if str(spec.key).strip().lower() == lookup:
            return spec
    raise ValueError(f"Evaluation provider key not registered: {key}")


def _build_provider_from_spec(spec: EvaluationSpec) -> object:
    key = str(spec.key).strip().lower()
    builder = _EVAL_PROVIDER_BUILDERS.get(key)
    if builder is None:
        raise ValueError(f"Unknown evaluation provider key: {spec.key}")
    params = dict(spec.params or {})
    return builder(params)


def build_evaluation_providers(registry: EvaluationRegistry, keys: Sequence[str]) -> list[object]:
    providers: list[object] = []
    for key in keys:
        spec = _find_spec(registry, key)
        providers.append(_build_provider_from_spec(spec))
    return providers


def register_evaluation_runtime(solver, registry: EvaluationRegistry, keys: Sequence[str]) -> None:
    register = getattr(solver, "register_evaluation_provider", None)
    if not callable(register):
        return
    for provider in build_evaluation_providers(registry, keys):
        register(provider)
