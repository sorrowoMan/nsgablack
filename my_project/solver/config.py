# -*- coding: utf-8 -*-
"""Solver-core configuration for this project (registry only)."""

from __future__ import annotations

from dataclasses import dataclass
from dataclasses import field
from dataclasses import fields
from typing import Any, Callable, Dict, Optional

from nsgablack.core.evolution_solver import EvolutionSolver


@dataclass(frozen=True)
class SolverCoreConfig:
    pop_size: int = 80
    max_generations: int = 60
    mutation_rate: float = 0.2
    crossover_rate: float = 0.8
    enable_progress_log: bool = True
    report_interval: int = 6
    thread_bias_isolation: str = "deepcopy"
    plugin_strict: bool = False


@dataclass(frozen=True)
class SolverProfileSpec:
    key: str
    params: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class SolverProfileRegistry:
    registry: tuple[SolverProfileSpec, ...] = ()


def get_solver_profile_registry() -> SolverProfileRegistry:
    return SolverProfileRegistry(
        registry=(
            SolverProfileSpec(
                key="default",
                params={
                    "pop_size": 80,
                    "max_generations": 60,
                    "mutation_rate": 0.2,
                    "crossover_rate": 0.8,
                    "enable_progress_log": True,
                    "report_interval": 6,
                    "thread_bias_isolation": "deepcopy",
                    "plugin_strict": False,
                },
            ),
        )
    )


ProfileBuilder = Callable[[Dict[str, Any]], SolverCoreConfig]

_SOLVER_PROFILE_BUILDERS: Dict[str, ProfileBuilder] = {}


def register_solver_profile_builder(key: str, builder: ProfileBuilder) -> None:
    _SOLVER_PROFILE_BUILDERS[str(key).strip().lower()] = builder


def _split_config_kwargs(config_cls, params: Dict[str, Any]) -> tuple[object, Dict[str, Any]]:
    if not params:
        return config_cls(), {}
    cfg_fields = {f.name for f in fields(config_cls)}
    cfg_kwargs = {k: v for k, v in params.items() if k in cfg_fields}
    other = {k: v for k, v in params.items() if k not in cfg_fields}
    return config_cls(**cfg_kwargs), other


def _build_profile_from_spec(spec: SolverProfileSpec) -> SolverCoreConfig:
    key = str(spec.key).strip().lower()
    builder = _SOLVER_PROFILE_BUILDERS.get(key)
    if builder is None:
        raise ValueError(f"Unknown solver profile key: {spec.key}")
    return builder(dict(spec.params or {}))


def build_solver_profile(registry: SolverProfileRegistry, key: str) -> SolverCoreConfig:
    lookup = str(key).strip().lower()
    for spec in tuple(registry.registry or ()):
        if str(spec.key).strip().lower() == lookup:
            return _build_profile_from_spec(spec)
    raise ValueError(f"Solver profile key not registered: {key}")


def apply_solver_core_config(solver, cfg: SolverCoreConfig) -> None:
    solver.pop_size = int(cfg.pop_size)
    solver.max_generations = int(cfg.max_generations)
    solver.mutation_rate = float(cfg.mutation_rate)
    solver.crossover_rate = float(cfg.crossover_rate)
    solver.enable_progress_log = bool(cfg.enable_progress_log)
    solver.report_interval = int(cfg.report_interval)
    solver.parallel_thread_bias_isolation = str(cfg.thread_bias_isolation)
    if hasattr(solver, "plugin_manager") and getattr(solver, "plugin_manager", None) is not None:
        try:
            solver.plugin_manager.strict = bool(cfg.plugin_strict)
        except Exception:
            pass


def apply_solver_profile(solver, registry: SolverProfileRegistry, key: str) -> None:
    cfg = build_solver_profile(registry, key)
    apply_solver_core_config(solver, cfg)


def _register_builtin_solver_profiles() -> None:
    def _default_builder(params: Dict[str, Any]) -> SolverCoreConfig:
        cfg, _ = _split_config_kwargs(SolverCoreConfig, params)
        return cfg

    register_solver_profile_builder("default", _default_builder)


_register_builtin_solver_profiles()


# --- Store profile (context/snapshot backends) ------------------------------
@dataclass(frozen=True)
class StoreProfile:
    context_store_backend: str = "memory"  # memory | redis
    context_store_redis_url: str = "redis://localhost:6379/0"
    context_store_key_prefix: str = "nsgablack:context"
    context_store_ttl_seconds: float | None = None

    snapshot_store_backend: str = "memory"  # memory | file | redis
    snapshot_store_redis_url: str = "redis://localhost:6379/0"
    snapshot_store_key_prefix: str = "nsgablack:snapshot"
    snapshot_store_ttl_seconds: float | None = None
    snapshot_store_dir: str | None = None
    snapshot_store_serializer: str = "safe"
    snapshot_store_hmac_env_var: str = "NSGABLACK_SNAPSHOT_HMAC_KEY"
    snapshot_store_unsafe_allow_unsigned: bool = False
    snapshot_store_max_payload_bytes: int = 8_388_608
    snapshot_schema: str = "population_snapshot_v1"


@dataclass(frozen=True)
class StoreProfileSpec:
    key: str
    params: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class StoreProfileRegistry:
    registry: tuple[StoreProfileSpec, ...] = ()


def get_store_profile_registry() -> StoreProfileRegistry:
    return StoreProfileRegistry(
        registry=(
            StoreProfileSpec(
                key="default",
                params={
                    "context_store_backend": "memory",
                    "snapshot_store_backend": "memory",
                },
            ),
        )
    )


def _build_store_profile(spec: StoreProfileSpec) -> StoreProfile:
    cfg, other = _split_config_kwargs(StoreProfile, dict(spec.params or {}))
    if other:
        raise ValueError(f"Unknown store profile params: {sorted(other.keys())}")
    return cfg


def build_store_profile(registry: StoreProfileRegistry, key: str) -> StoreProfile:
    lookup = str(key).strip().lower()
    for spec in tuple(registry.registry or ()):
        if str(spec.key).strip().lower() == lookup:
            return _build_store_profile(spec)
    raise ValueError(f"Store profile key not registered: {key}")


def create_evolution_solver(
    problem: Any,
    *,
    bias_module: Any = None,
    store_registry: StoreProfileRegistry,
    store_key: str = "default",
) -> EvolutionSolver:
    store = build_store_profile(store_registry, store_key)
    return EvolutionSolver(
        problem,
        bias_module=bias_module,
        context_store_backend=str(store.context_store_backend),
        context_store_redis_url=str(store.context_store_redis_url),
        context_store_key_prefix=str(store.context_store_key_prefix),
        context_store_ttl_seconds=store.context_store_ttl_seconds,
        snapshot_store_backend=str(store.snapshot_store_backend),
        snapshot_store_redis_url=str(store.snapshot_store_redis_url),
        snapshot_store_key_prefix=str(store.snapshot_store_key_prefix),
        snapshot_store_ttl_seconds=store.snapshot_store_ttl_seconds,
        snapshot_store_dir=store.snapshot_store_dir,
        snapshot_store_serializer=str(store.snapshot_store_serializer),
        snapshot_store_hmac_env_var=str(store.snapshot_store_hmac_env_var),
        snapshot_store_unsafe_allow_unsigned=bool(store.snapshot_store_unsafe_allow_unsigned),
        snapshot_store_max_payload_bytes=int(store.snapshot_store_max_payload_bytes),
        snapshot_schema=str(store.snapshot_schema),
    )
