from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

from .context_keys import normalize_context_key

_REQUIRES_ATTRS = ("context_requires", "requires_context_keys", "runtime_requires")
_PROVIDES_ATTRS = ("context_provides", "provides_context_keys", "runtime_provides")
_MUTATES_ATTRS = ("context_mutates", "mutates_context_keys", "runtime_mutates")
_CACHE_ATTRS = ("context_cache", "cache_context_keys", "runtime_cache")
_NOTES_ATTRS = (
    "context_notes",
    "recommended_mutators",
    "recommended_plugins",
    "companions",
    "recommended_suite",
)


def _normalize_fields(items: Optional[Iterable[Any]]) -> List[str]:
    if not items:
        return []
    out: List[str] = []
    for item in items:
        if item is None:
            continue
        text = normalize_context_key(str(item))
        if text:
            out.append(text)
    return sorted(set(out))


def _normalize_notes(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, str):
        text = value.strip()
        return text or None
    if isinstance(value, Mapping):
        parts = []
        for k, v in value.items():
            key = str(k).strip()
            val = _normalize_notes(v)
            if not key or not val:
                continue
            parts.append(f"{key}: {val}")
        return "; ".join(parts) or None
    if isinstance(value, (list, tuple, set)):
        parts = []
        for item in value:
            text = _normalize_notes(item)
            if text:
                parts.append(text)
        return "; ".join(parts) or None
    text = str(value).strip()
    return text or None


def _collect_attrs(obj: Any, names: Sequence[str]) -> List[Any]:
    out: List[Any] = []
    for name in names:
        value = getattr(obj, name, None)
        if value is None:
            continue
        out.append(value)
    return out


def _merge_notes(*values: Any) -> Optional[str]:
    parts: List[str] = []
    for value in values:
        text = _normalize_notes(value)
        if not text:
            continue
        parts.append(text)
    if not parts:
        return None
    # Keep deterministic order while removing duplicates.
    uniq: List[str] = []
    seen = set()
    for item in parts:
        if item in seen:
            continue
        seen.add(item)
        uniq.append(item)
    return " | ".join(uniq)


def _flatten_values(values: Sequence[Any]) -> List[Any]:
    out: List[Any] = []
    for value in values:
        if value is None:
            continue
        if isinstance(value, (list, tuple, set)):
            out.extend(list(value))
        else:
            out.append(value)
    return out


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
            notes = _merge_notes(
                value.get("notes"),
                value.get("context_notes"),
                value.get("recommended_mutators"),
                value.get("recommended_plugins"),
                value.get("companions"),
                value.get("recommended_suite"),
            )
            return ContextContract(
                requires=list(value.get("requires", ()) or ())
                + list(value.get("context_requires", ()) or ())
                + list(value.get("requires_context_keys", ()) or ())
                + list(value.get("runtime_requires", ()) or ()),
                provides=list(value.get("provides", ()) or ())
                + list(value.get("context_provides", ()) or ())
                + list(value.get("provides_context_keys", ()) or ())
                + list(value.get("runtime_provides", ()) or ()),
                mutates=list(value.get("mutates", ()) or ())
                + list(value.get("context_mutates", ()) or ())
                + list(value.get("mutates_context_keys", ()) or ())
                + list(value.get("runtime_mutates", ()) or ()),
                cache=list(value.get("cache", ()) or ())
                + list(value.get("context_cache", ()) or ())
                + list(value.get("cache_context_keys", ()) or ())
                + list(value.get("runtime_cache", ()) or ()),
                notes=notes,
            ).normalized()

    requires_values = _collect_attrs(obj, _REQUIRES_ATTRS)
    provides_values = _collect_attrs(obj, _PROVIDES_ATTRS)
    mutates_values = _collect_attrs(obj, _MUTATES_ATTRS)
    cache_values = _collect_attrs(obj, _CACHE_ATTRS)
    notes = _merge_notes(*_collect_attrs(obj, _NOTES_ATTRS))

    if any([requires_values, provides_values, mutates_values, cache_values, notes]):
        return ContextContract(
            requires=_flatten_values(requires_values),
            provides=_flatten_values(provides_values),
            mutates=_flatten_values(mutates_values),
            cache=_flatten_values(cache_values),
            notes=notes,
        ).normalized()
    return None


def collect_solver_contracts(solver: Any) -> List[Tuple[str, ContextContract]]:
    contracts: List[Tuple[str, ContextContract]] = []
    seen: set[Tuple[str, int]] = set()

    def _add(name: str, obj: Any) -> None:
        if obj is None:
            return
        marker = (str(name), id(obj))
        if marker in seen:
            return
        seen.add(marker)
        contract = get_component_contract(obj)
        if contract is not None:
            contracts.append((name, contract))

    _add("representation_pipeline", getattr(solver, "representation_pipeline", None))
    _add("bias_module", getattr(solver, "bias_module", None))
    adapter = getattr(solver, "adapter", None)
    _add("adapter", adapter)
    if adapter is not None:
        for idx, spec in enumerate(getattr(adapter, "strategies", ()) or ()):
            sub = getattr(spec, "adapter", None)
            name = str(getattr(spec, "name", f"strategy_{idx}"))
            _add(f"adapter.strategy.{name}", sub)
        for idx, role in enumerate(getattr(adapter, "roles", ()) or ()):
            role_name = str(getattr(role, "name", f"role_{idx}"))
            role_adapter = getattr(role, "adapter", None)
            _add(f"adapter.role.{role_name}", role_adapter if not callable(role_adapter) else None)
        for unit in getattr(adapter, "units", ()) or ():
            role_name = str(getattr(unit, "role", "role"))
            unit_id = int(getattr(unit, "unit_id", 0))
            _add(f"adapter.unit.{role_name}#{unit_id}", getattr(unit, "adapter", None))

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


def detect_context_conflicts(
    contracts: Sequence[Tuple[str, ContextContract]],
) -> List[str]:
    """Detect potential multi-writer risks on the same context key.

    This is a static contract-level detector:
    - It does not execute the solver.
    - It warns when one key has multiple providers/mutators.
    """
    writers_by_key: Dict[str, List[str]] = {}
    for name, contract in contracts:
        keys = set(contract.provides) | set(contract.mutates)
        for key in keys:
            k = str(key).strip()
            if not k:
                continue
            writers_by_key.setdefault(k, []).append(str(name))

    issues: List[str] = []
    for key, writers in sorted(writers_by_key.items(), key=lambda x: x[0]):
        unique = sorted(set(writers))
        if len(unique) <= 1:
            continue
        issues.append(f"{key}: " + ", ".join(unique))
    return issues
