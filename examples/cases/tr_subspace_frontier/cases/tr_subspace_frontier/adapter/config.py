# -*- coding: utf-8 -*-
# Search-layer configuration (adapter registry + orchestration defaults).

from __future__ import annotations

from dataclasses import dataclass
from dataclasses import field
from typing import Any, Callable, Dict, Optional, Sequence

from nsgablack.adapters import (
    AsyncEventDrivenAdapter,
    AsyncEventDrivenConfig,
    EventCaseSpec,
    EventStrategySpec,
    MultiStrategyConfig,
    SerialPhaseSpec,
    SerialStrategyConfig,
    StrategyChainAdapter,
    StrategyRouterAdapter,
    StrategySpec,
)

from .example_adapter import ExampleAdapter


@dataclass(frozen=True)
class AdapterSpec:
    key: str
    params: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class OrchestrationDefaults:
    multi: MultiStrategyConfig = field(default_factory=MultiStrategyConfig)
    serial: SerialStrategyConfig = field(default_factory=SerialStrategyConfig)
    event: AsyncEventDrivenConfig = field(default_factory=AsyncEventDrivenConfig)


@dataclass(frozen=True)
class AdapterRegistry:
    registry: tuple[AdapterSpec, ...] = ()
    orchestration: OrchestrationDefaults = field(default_factory=OrchestrationDefaults)


def get_adapter_registry() -> AdapterRegistry:
    return AdapterRegistry(
        registry=(
            AdapterSpec(key="example_adapter", params={"max_candidates": 8, "seed": 0}),
        )
    )


AdapterBuilder = Callable[[Dict[str, Any]], object]

_ADAPTER_BUILDERS: Dict[str, AdapterBuilder] = {}


def register_adapter_builder(key: str, builder: AdapterBuilder) -> None:
    _ADAPTER_BUILDERS[str(key).strip().lower()] = builder


def _find_spec(registry: AdapterRegistry, key: str) -> Optional[AdapterSpec]:
    lookup = str(key).strip().lower()
    for spec in tuple(registry.registry or ()):
        if str(spec.key).strip().lower() == lookup:
            return spec
    return None


def build_adapter_instance(registry: AdapterRegistry, adapter_key: str) -> object | None:
    spec = _find_spec(registry, adapter_key)
    if spec is None:
        return None
    key = str(spec.key).strip().lower()
    builder = _ADAPTER_BUILDERS.get(key)
    if builder is None:
        raise ValueError(f"Unknown adapter key: {spec.key}")
    params = dict(spec.params or {})
    return builder(params)


def require_adapter(registry: AdapterRegistry, adapter_key: str) -> object:
    adapter = build_adapter_instance(registry, adapter_key)
    if adapter is None:
        raise ValueError(f"Adapter key not registered: {adapter_key}")
    return adapter


# --- Orchestration language (pure compose, no parameter setting) -----------
ValueRef = Any | Callable[[dict], Any]
Cond = Callable[[dict], bool]


def val(value: Any) -> Callable[[dict], Any]:
    return lambda _c: value


def _resolve(ref: ValueRef, ctx: dict) -> Any:
    return ref(ctx) if callable(ref) else ref


def _safe(op: Callable[[Any, Any], bool], left: ValueRef, right: ValueRef) -> Cond:
    def _fn(c: dict) -> bool:
        try:
            return bool(op(_resolve(left, c), _resolve(right, c)))
        except (TypeError, ValueError, KeyError, IndexError, AttributeError, ArithmeticError):
            return False

    return _fn


def all_of(*conds: Cond) -> Cond:
    return lambda c: all(bool(cond(c)) for cond in conds)


def any_of(*conds: Cond) -> Cond:
    return lambda c: any(bool(cond(c)) for cond in conds)


def not_(cond: Cond) -> Cond:
    return lambda c: not bool(cond(c))


def _ctx_get(ctx: dict, path: str) -> Any:
    text = str(path)
    if isinstance(ctx, dict) and text in ctx:
        return ctx.get(text)
    cur: Any = ctx
    for part in text.split("."):
        if isinstance(cur, dict) and part in cur:
            cur = cur.get(part)
            continue
        return None
    return cur


def ctx(path: str) -> Callable[[dict], Any]:
    return lambda c: _ctx_get(c, path)


def truthy(ref: ValueRef) -> Cond:
    return lambda c: bool(_resolve(ref, c))


def exists(ref: ValueRef) -> Cond:
    return lambda c: _resolve(ref, c) is not None


def eq(left: ValueRef, right: ValueRef) -> Cond:
    return _safe(lambda a, b: a == b, left, right)


def ne(left: ValueRef, right: ValueRef) -> Cond:
    return _safe(lambda a, b: a != b, left, right)


def gt(left: ValueRef, right: ValueRef) -> Cond:
    return _safe(lambda a, b: a > b, left, right)


def ge(left: ValueRef, right: ValueRef) -> Cond:
    return _safe(lambda a, b: a >= b, left, right)


def lt(left: ValueRef, right: ValueRef) -> Cond:
    return _safe(lambda a, b: a < b, left, right)


def le(left: ValueRef, right: ValueRef) -> Cond:
    return _safe(lambda a, b: a <= b, left, right)


def in_(left: ValueRef, right: ValueRef) -> Cond:
    return _safe(lambda a, b: a in b, left, right)


def not_in(left: ValueRef, right: ValueRef) -> Cond:
    return _safe(lambda a, b: a not in b, left, right)


def between(value: ValueRef, low: ValueRef, high: ValueRef) -> Cond:
    return all_of(ge(value, low), le(value, high))


def custom(fn: Callable[[dict], bool]) -> Cond:
    return fn


def group(registry: AdapterRegistry, name: str, adapter_keys: Sequence[str]) -> object:
    specs: list[StrategySpec] = []
    for key in adapter_keys:
        adapter = require_adapter(registry, key)
        specs.append(StrategySpec(adapter=adapter, name=str(key)))
    if len(specs) == 1:
        return specs[0].adapter
    base_cfg = registry.orchestration.multi or MultiStrategyConfig()
    return StrategyRouterAdapter(strategies=specs, config=base_cfg, name=str(name))


def multi(registry: AdapterRegistry, name: str, adapters: Sequence[object]) -> object:
    items = [a for a in adapters if a is not None]
    if len(items) == 1:
        return items[0]
    specs = [StrategySpec(adapter=a, name=getattr(a, "name", f"adapter_{i}")) for i, a in enumerate(items)]
    base_cfg = registry.orchestration.multi or MultiStrategyConfig()
    return StrategyRouterAdapter(strategies=specs, config=base_cfg, name=str(name))


def phase(name: str, adapter: object, *, steps: int = -1, advance_when: Cond | None = None):
    return SerialPhaseSpec(name=str(name), adapter=adapter, steps=int(steps), advance_when=advance_when)


def serial(registry: AdapterRegistry, name: str, phases: Sequence[SerialPhaseSpec]) -> object:
    items = [p for p in phases if p is not None]
    if len(items) == 1:
        return items[0].adapter
    base_cfg = registry.orchestration.serial or SerialStrategyConfig()
    return StrategyChainAdapter(phases=items, config=base_cfg, name=str(name))


def event_case(
    name: str,
    adapter: object,
    *,
    when: Cond | None = None,
    when_dsl: Dict[str, Any] | None = None,
    priority: int = 0,
    cooldown_generations: int = 0,
    min_active_generations: int = 0,
    report_fields: Sequence[str] = (),
    weight: float = 1.0,
    enabled: bool = True,
) -> EventCaseSpec:
    fields = (report_fields,) if isinstance(report_fields, str) else tuple(report_fields or ())
    return EventCaseSpec(
        adapter=adapter,
        name=str(name),
        weight=float(weight),
        enabled=bool(enabled),
        when=when,
        when_dsl=when_dsl,
        priority=int(priority),
        cooldown_generations=int(cooldown_generations),
        min_active_generations=int(min_active_generations),
        report_fields=fields,
    )


def event(registry: AdapterRegistry, name: str, adapters: Sequence[object]) -> object:
    items = [a for a in adapters if a is not None]
    if len(items) == 1 and not isinstance(items[0], EventStrategySpec):
        return items[0]
    specs = []
    for i, item in enumerate(items):
        if isinstance(item, EventStrategySpec):
            specs.append(item)
            continue
        specs.append(EventStrategySpec(adapter=item, name=getattr(item, "name", f"adapter_{i}"), weight=1.0, enabled=True))
    base_cfg = registry.orchestration.event or AsyncEventDrivenConfig()
    return AsyncEventDrivenAdapter(strategies=specs, config=base_cfg, name=str(name))


# --- Example: registering a new adapter ------------------------------------
@dataclass(frozen=True)
class ExampleAdapterConfig:
    max_candidates: int = 8
    seed: int = 0


def build_example_adapter(cfg: ExampleAdapterConfig) -> ExampleAdapter:
    return ExampleAdapter(max_candidates=cfg.max_candidates, seed=cfg.seed)


def _register_builtin_adapters() -> None:
    register_adapter_builder("example_adapter", lambda p: ExampleAdapter(**p))


_register_builtin_adapters()
