from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple


def _normalize_fields(items: Optional[Iterable[Any]]) -> List[str]:
    if not items:
        return []
    out: List[str] = []
    for item in items:
        if item is None:
            continue
        out.append(str(item))
    return sorted(set(out))


@dataclass(frozen=True)
class ContextContract:
    requires: Sequence[str] = field(default_factory=tuple)
    provides: Sequence[str] = field(default_factory=tuple)
    mutates: Sequence[str] = field(default_factory=tuple)
    cache: Sequence[str] = field(default_factory=tuple)
    notes: Optional[str] = None

    def normalized(self) -> "ContextContract":
        return ContextContract(
            requires=_normalize_fields(self.requires),
            provides=_normalize_fields(self.provides),
            mutates=_normalize_fields(self.mutates),
            cache=_normalize_fields(self.cache),
            notes=self.notes,
        )

    def to_dict(self) -> Dict[str, Any]:
        norm = self.normalized()
        return {
            "requires": list(norm.requires),
            "provides": list(norm.provides),
            "mutates": list(norm.mutates),
            "cache": list(norm.cache),
            "notes": norm.notes,
        }

    def merge(self, other: "ContextContract") -> "ContextContract":
        a = self.normalized()
        b = other.normalized()
        return ContextContract(
            requires=sorted(set(a.requires) | set(b.requires)),
            provides=sorted(set(a.provides) | set(b.provides)),
            mutates=sorted(set(a.mutates) | set(b.mutates)),
            cache=sorted(set(a.cache) | set(b.cache)),
            notes=None,
        )


def get_component_contract(obj: Any) -> Optional[ContextContract]:
    if obj is None:
        return None
    getter = getattr(obj, "get_context_contract", None)
    if callable(getter):
        try:
            value = getter()
        except Exception:
            value = None
        if isinstance(value, ContextContract):
            return value.normalized()
        if isinstance(value, Mapping):
            return ContextContract(
                requires=value.get("requires"),
                provides=value.get("provides"),
                mutates=value.get("mutates"),
                cache=value.get("cache") or value.get("context_cache"),
                notes=value.get("notes"),
            ).normalized()

    requires = getattr(obj, "context_requires", None)
    provides = getattr(obj, "context_provides", None)
    mutates = getattr(obj, "context_mutates", None)
    cache = getattr(obj, "context_cache", None)
    notes = getattr(obj, "context_notes", None)

    if any([requires, provides, mutates, cache, notes]):
        return ContextContract(
            requires=requires,
            provides=provides,
            mutates=mutates,
            cache=cache,
            notes=notes,
        ).normalized()
    return None


def collect_solver_contracts(solver: Any) -> List[Tuple[str, ContextContract]]:
    contracts: List[Tuple[str, ContextContract]] = []

    def _add(name: str, obj: Any) -> None:
        contract = get_component_contract(obj)
        if contract is not None:
            contracts.append((name, contract))

    _add("representation_pipeline", getattr(solver, "representation_pipeline", None))
    _add("bias_module", getattr(solver, "bias_module", None))
    _add("adapter", getattr(solver, "adapter", None))

    plugin_manager = getattr(solver, "plugin_manager", None)
    if plugin_manager is not None:
        plugins = getattr(plugin_manager, "plugins", None) or []
        for plugin in plugins:
            name = getattr(plugin, "name", plugin.__class__.__name__)
            _add(f"plugin.{name}", plugin)

    return contracts


def validate_context_contracts(
    contracts: Sequence[Tuple[str, ContextContract]],
    context: Mapping[str, Any],
) -> List[str]:
    warnings: List[str] = []
    ctx_keys = set(context.keys())
    for name, contract in contracts:
        missing = [k for k in contract.requires if k not in ctx_keys]
        if missing:
            warnings.append(f"{name} missing required context keys: {', '.join(missing)}")
    return warnings
