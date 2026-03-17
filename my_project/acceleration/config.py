# -*- coding: utf-8 -*-
"""L0 acceleration configuration for this project (registry only)."""

from __future__ import annotations

from dataclasses import dataclass
from dataclasses import field
from typing import Any, Dict, Sequence

from nsgablack.core import GpuBackend, ProcessPoolBackend, ThreadPoolBackend


@dataclass(frozen=True)
class AccelerationSpec:
    key: str
    params: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class AccelerationRegistry:
    registry: tuple[AccelerationSpec, ...] = ()


def get_acceleration_registry() -> AccelerationRegistry:
    return AccelerationRegistry(
        registry=(
            AccelerationSpec(key="thread", params={"scope": "evaluation", "workers": None}),
            AccelerationSpec(key="process", params={"scope": "evaluation", "workers": None}),
            AccelerationSpec(key="gpu", params={"scope": "evaluation", "gpu_backend": "auto", "gpu_device": "cuda:0"}),
        )
    )


def _find_spec(registry: AccelerationRegistry, key: str) -> AccelerationSpec:
    lookup = str(key).strip().lower()
    for spec in tuple(registry.registry or ()):
        if str(spec.key).strip().lower() == lookup:
            return spec
    raise ValueError(f"Acceleration key not registered: {key}")


def _set_default_backend(solver, scope: str, backend: str) -> None:
    setter = getattr(solver, "set_acceleration_default_backend", None)
    if callable(setter):
        setter(scope=scope, backend=backend)


def _register_backend(solver, spec: AccelerationSpec) -> tuple[str, str] | None:
    key = str(spec.key).strip().lower()
    params = dict(spec.params or {})
    scope = str(params.pop("scope", "evaluation"))
    if key == "thread":
        solver.register_acceleration_backend(
            scope=scope,
            backend="thread",
            factory=lambda: ThreadPoolBackend(max_workers=params.get("workers")),
        )
        return scope, "thread"
    if key == "process":
        solver.register_acceleration_backend(
            scope=scope,
            backend="process",
            factory=lambda: ProcessPoolBackend(max_workers=params.get("workers")),
        )
        return scope, "process"
    if key == "gpu":
        solver.register_acceleration_backend(
            scope=scope,
            backend="gpu",
            factory=lambda: GpuBackend(
                preferred_backend=str(params.get("gpu_backend", "auto")),
                device=str(params.get("gpu_device", "cuda:0")),
            ),
        )
        return scope, "gpu"
    if key == "none":
        return None
    raise ValueError(f"Unknown acceleration backend key: {spec.key}")


def apply_acceleration_backends(
    solver,
    registry: AccelerationRegistry,
    keys: Sequence[str],
) -> None:
    default_set = False
    first_registered: tuple[str, str] | None = None
    for key in keys:
        spec = _find_spec(registry, key)
        reg = _register_backend(solver, spec)
        if reg is None:
            continue
        if first_registered is None:
            first_registered = reg
        params = dict(spec.params or {})
        if bool(params.get("default")):
            _set_default_backend(solver, scope=reg[0], backend=reg[1])
            default_set = True
    if not default_set and first_registered is not None:
        _set_default_backend(solver, scope=first_registered[0], backend=first_registered[1])
