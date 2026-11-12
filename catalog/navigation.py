"""Presentation groups for Catalog browsing, independent of component ownership.

The stored ``CatalogEntry.kind`` remains authoritative. ``group:*`` values are
only restorable UI scopes and are translated into the existing kind filter.
No model, component import, or AI classification participates in this mapping.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass


@dataclass(frozen=True)
class NavigationGroup:
    key: str
    title: str
    kinds: tuple[str, ...]


GROUPS = (
    NavigationGroup("search", "算法策略", ("adapter",)),
    NavigationGroup("problem", "问题与偏好", ("problem", "problem_bridge", "bias")),
    NavigationGroup("pipeline", "数据与候选管线", (
        "representation", "pipeline", "data_view", "schema", "numericizer",
        "conditional", "symbolic_pipeline",
    )),
    NavigationGroup("model", "模型与编解码", ("model", "codec", "head")),
    NavigationGroup("assembly", "装配与编排", (
        "assembly", "preset", "trainer", "integration", "nsgablack_neural",
        "nsgablack_symbolic", "suite",
    )),
    NavigationGroup("runtime", "运行与后端", (
        "plugin", "capability", "backend", "backend_capability", "provider", "experiment",
    )),
    NavigationGroup("tools", "协议与工具", ("core", "tool", "catalog", "dashboard")),
    NavigationGroup("learning", "示例与文档", ("example", "doc")),
)
_BY_KEY = {f"group:{group.key}": group for group in GROUPS}
_BY_KIND = {kind: f"group:{group.key}" for group in GROUPS for kind in group.kinds}
PRIMARY_OPTIONS = ("all", *_BY_KEY)


def is_group(value: str | None) -> bool:
    return str(value or "").strip().lower() in _BY_KEY


def group_for_kind(kind: str | None) -> str:
    value = str(kind or "all").strip().lower()
    if value == "all" or is_group(value):
        return value
    return _BY_KIND.get(value, "group:tools")


def group_title(value: str) -> str:
    group = _BY_KEY.get(str(value or "").strip().lower())
    return group.title if group is not None else "全部组件"


def member_kinds(group: str, available_kinds: Sequence[str]) -> tuple[str, ...]:
    """Return only published kinds, including new kinds in the tools fallback."""
    values = {str(kind).strip().lower() for kind in available_kinds if str(kind).strip()}
    return tuple(sorted(kind for kind in values if group_for_kind(kind) == group))


def contains_kind(scope: str, kind: str) -> bool:
    return scope == "all" or scope == kind or (is_group(scope) and group_for_kind(kind) == scope)


def group_counts(by_kind: Mapping[str, int]) -> dict[str, int]:
    counts = {scope: 0 for scope in PRIMARY_OPTIONS}
    for kind, value in by_kind.items():
        count = int(value)
        counts["all"] += count
        counts[group_for_kind(kind)] += count
    return counts


def query_scope(
    scope: str | None,
    field_filters: Mapping[str, object] | None = None,
    *,
    available_kinds: Sequence[str] = (),
) -> tuple[str | None, dict[str, object]]:
    """Translate one UI scope for every list, search, and facet read.

    Existing field filters compose by intersection with a group; they never
    override its kind boundary. A disjoint intersection deliberately matches
    no real kind instead of becoming an unfiltered query.
    """
    value = str(scope or "all").strip().lower()
    filters = dict(field_filters or {})
    if not is_group(value):
        return (None if value == "all" else value), filters
    kinds = member_kinds(value, available_kinds) if available_kinds else _BY_KEY[value].kinds
    if "kind" in filters:
        raw = filters["kind"]
        expected = {str(item).strip().lower() for item in
                    (raw.split(",") if isinstance(raw, str) else raw)}
        kinds = tuple(kind for kind in kinds if kind in expected)
    filters["kind"] = kinds or ("__catalog_navigation_empty__",)
    return None, filters
