from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from nsgablack.project.catalog import find_project_root, load_project_entries

from .contract_relations import build_contract_neighbor_sections
from .registry import Catalog, CatalogEntry, get_catalog
from .store import catalog_db_config_backend, catalog_db_config_enabled, catalog_db_config_info, catalog_db_config_mode, resolve_catalog_store
from .usage import build_usage_profile, enrich_context_contracts, enrich_usage_contracts

_CATALOG_FIELD_ORDER: tuple[str, ...] = (
    "key",
    "title",
    "kind",
    "import_path",
    "module",
    "symbol",
    "tags",
    "summary",
    "companions",
    "context_requires",
    "context_provides",
    "context_mutates",
    "context_cache",
    "context_notes",
    "artifact_requires",
    "artifact_provides",
    "phase_in",
    "phase_out",
    "use_when",
    "minimal_wiring",
    "required_companions",
    "config_keys",
    "example_entry",
)

_FIELD_GROUPS: dict[str, tuple[str, ...]] = {
    "base": ("key", "title", "kind", "import_path", "module", "symbol", "tags", "summary", "companions"),
    "contracts": (
        "context_requires",
        "context_provides",
        "context_mutates",
        "context_cache",
        "context_notes",
        "artifact_requires",
        "artifact_provides",
        "phase_in",
        "phase_out",
    ),
    "usage": ("use_when", "minimal_wiring", "required_companions", "config_keys", "example_entry"),
}

_DEFAULT_FACET_FIELDS: dict[str, tuple[str, ...]] = {
    "adapter": ("tags", "companions", "required_companions", "context_provides", "artifact_provides", "phase_out"),
    "plugin": ("tags", "companions", "context_requires", "context_provides", "artifact_provides", "phase_out"),
    "bias": ("tags", "companions", "required_companions", "context_provides", "artifact_provides", "phase_out"),
    "representation": ("tags", "companions", "context_requires", "context_provides", "artifact_requires", "phase_in"),
    "resource": ("tags", "companions", "context_provides", "artifact_provides"),
    "backend": ("tags", "companions", "context_provides", "artifact_provides"),
    "suite": ("tags", "companions", "required_companions"),
    "tool": ("tags", "companions"),
    "doc": ("tags",),
    "example": ("tags", "companions"),
}


@dataclass(frozen=True)
class CatalogContext:
    catalog: Catalog
    scope: str
    profile: str
    project_root: str | None
    include_global: bool
    project_found: bool
    effective_source: str


@dataclass(frozen=True)
class CatalogReadRoute:
    profile: str
    source_mode: str
    effective_source: str
    db_store: Any | None
    db_backend: str | None = None
    db_error: str | None = None
    explicit_db_path: bool = False
    config_enabled: bool = False


def _normalize_kind(kind: str | None) -> str | None:
    raw = str(kind or "").strip().lower()
    return raw or None


def _normalize_scope(scope: str | None) -> str:
    raw = str(scope or "framework").strip().lower()
    return "project" if raw == "project" else "framework"


def _normalize_field(field: str | None) -> str:
    raw = str(field or "all").strip().lower()
    return raw if raw in {"all", "name", "tag", "context", "usage"} else "all"


def _normalize_strings(values: object) -> tuple[str, ...]:
    if values is None:
        return ()
    if isinstance(values, str):
        parts = [part.strip() for part in str(values).split(",")]
        return tuple(part for part in parts if part)
    if isinstance(values, Mapping):
        return tuple(str(key).strip() for key in values.keys() if str(key).strip())
    if isinstance(values, (list, tuple, set, frozenset)):
        out: list[str] = []
        for value in values:
            out.extend(_normalize_strings(value))
        return tuple(out)
    text = str(values).strip()
    return (text,) if text else ()


def _normalize_field_filters(
    field_filters: Mapping[str, object] | Sequence[tuple[str, object]] | None,
) -> dict[str, tuple[str, ...]]:
    if not field_filters:
        return {}
    items = field_filters.items() if isinstance(field_filters, Mapping) else field_filters
    out: dict[str, tuple[str, ...]] = {}
    for name, value in items:
        key = str(name).strip()
        if not key:
            continue
        values = _normalize_strings(value)
        if values:
            out[key] = values
    return out


def _normalize_mode(mode: str | None) -> str:
    raw = str(mode or "").strip().lower()
    if raw in {"only", "prefer", "off"}:
        return raw
    if raw == "disabled":
        return "off"
    return "prefer"


def _resolve_read_route(
    *,
    profile: str | None = None,
    db_path: str | None = None,
    source_mode: str | None = None,
) -> CatalogReadRoute:
    profile_name = str(profile or "default")
    mode = _normalize_mode(source_mode if source_mode is not None else catalog_db_config_mode())
    explicit_db_path = bool(str(db_path or "").strip())
    config_enabled = bool(catalog_db_config_enabled())

    if explicit_db_path:
        target = str(db_path or "").strip()
        try:
            store = resolve_catalog_store(url=target, readonly=True)
            store.list_catalog_entries(profile=profile_name, limit=1)
            profile_check = getattr(store, "has_profile", None)
            if callable(profile_check) and not bool(profile_check(profile=profile_name)):
                raise RuntimeError(f"Catalog DB profile not materialized: {profile_name}")
            backend = str(getattr(store, "backend", "db") or "db")
            return CatalogReadRoute(
                profile=profile_name,
                source_mode="only",
                effective_source=backend,
                db_store=store,
                db_backend=backend,
                explicit_db_path=True,
                config_enabled=True,
            )
        except Exception as exc:
            if mode == "only":
                raise
            return CatalogReadRoute(
                profile=profile_name,
                source_mode=mode,
                effective_source="registry",
                db_store=None,
                db_backend=None,
                db_error=str(exc),
                explicit_db_path=True,
                config_enabled=True,
            )

    if mode == "off" or not config_enabled:
        return CatalogReadRoute(
            profile=profile_name,
            source_mode=mode,
            effective_source="registry",
            db_store=None,
            db_backend=None,
            config_enabled=config_enabled,
        )

    try:
        store = resolve_catalog_store(readonly=True)
        store.list_catalog_entries(profile=profile_name, limit=1)
        profile_check = getattr(store, "has_profile", None)
        if callable(profile_check) and not bool(profile_check(profile=profile_name)):
            raise RuntimeError(f"Catalog DB profile not materialized: {profile_name}")
        backend = str(getattr(store, "backend", "db") or "db")
        return CatalogReadRoute(
            profile=profile_name,
            source_mode=mode,
            effective_source=backend,
            db_store=store,
            db_backend=backend,
            config_enabled=True,
        )
    except Exception as exc:
        if mode == "only":
            raise
        return CatalogReadRoute(
            profile=profile_name,
            source_mode=mode,
            effective_source="registry",
            db_store=None,
            db_backend=None,
            db_error=str(exc),
            config_enabled=True,
        )


def _framework_source_info() -> dict[str, Any]:
    info: dict[str, Any] = {
        "db_enabled": False,
        "db_mode": "off",
        "db_backend": None,
        "mysql_enabled": False,
        "mysql_mode": "off",
        "postgres_enabled": False,
        "provider_active": False,
        "framework_source": "registry",
    }
    try:
        enabled = bool(catalog_db_config_enabled())
        mode = str(catalog_db_config_mode()).strip().lower()
        backend = catalog_db_config_backend()
        info["db_enabled"] = enabled
        info["db_mode"] = mode
        info["db_backend"] = backend
        info["mysql_enabled"] = backend == "mysql" and enabled
        info["mysql_mode"] = mode if backend == "mysql" else "off"
        info["postgres_enabled"] = backend == "postgresql" and enabled
        info["provider_active"] = enabled and mode != "off"
        if enabled and mode == "only":
            info["framework_source"] = str(backend or "db")
        elif enabled and mode != "off":
            info["framework_source"] = f"registry+{str(backend or 'db')}"
    except Exception:
        pass
    return info


def _resolve_project_root(project_path: str | Path | None) -> Path | None:
    start = Path(project_path).resolve() if project_path else Path.cwd().resolve()
    return find_project_root(start)


def _build_project_catalog(project_root: Path, *, profile: str | None = None, include_global: bool = False) -> Catalog:
    local_entries = enrich_context_contracts(
        load_project_entries(project_root),
        kinds=("plugin", "adapter", "bias", "representation"),
    )
    local_entries = enrich_usage_contracts(local_entries)
    if not include_global:
        return Catalog(local_entries)
    global_entries = get_catalog(profile=profile).list()
    local_keys = {entry.key for entry in local_entries}
    merged = list(local_entries) + [entry for entry in global_entries if entry.key not in local_keys]
    merged = enrich_context_contracts(
        merged,
        kinds=("plugin", "adapter", "bias", "representation"),
    )
    return Catalog(enrich_usage_contracts(merged))


def _load_catalog_context(
    *,
    profile: str | None = None,
    scope: str | None = None,
    project_path: str | Path | None = None,
    include_global: bool = False,
) -> CatalogContext:
    normalized_profile = str(profile or "default")
    normalized_scope = _normalize_scope(scope)
    if normalized_scope == "framework":
        return CatalogContext(
            catalog=get_catalog(profile=profile),
            scope="framework",
            profile=normalized_profile,
            project_root=None,
            include_global=False,
            project_found=True,
            effective_source="framework",
        )

    project_root = _resolve_project_root(project_path)
    if project_root is None:
        return CatalogContext(
            catalog=Catalog([]),
            scope="project",
            profile=normalized_profile,
            project_root=None,
            include_global=bool(include_global),
            project_found=False,
            effective_source="project-missing",
        )

    effective_source = "project+framework" if include_global else "project"
    return CatalogContext(
        catalog=_build_project_catalog(project_root, profile=profile, include_global=include_global),
        scope="project",
        profile=normalized_profile,
        project_root=str(project_root),
        include_global=bool(include_global),
        project_found=True,
        effective_source=effective_source,
    )


def _project_entries(
    *,
    profile: str | None = None,
    project_path: str | Path | None = None,
    include_global: bool = False,
    db_path: str | None = None,
    source_mode: str | None = None,
) -> tuple[list[CatalogEntry], CatalogContext]:
    context = _load_catalog_context(
        profile=profile,
        scope="project",
        project_path=project_path,
        include_global=False,
    )
    local_entries = _hydrate_entries(context.catalog.list(), catalog=context.catalog)
    if not include_global or not context.project_found:
        return local_entries, context
    global_entries = list_entries(
        profile=profile,
        scope="framework",
        include_global=False,
        limit=None,
        db_path=db_path,
        source_mode=source_mode,
    )
    local_keys = {entry.key.lower() for entry in local_entries}
    merged = list(local_entries) + [entry for entry in global_entries if entry.key.lower() not in local_keys]
    merged_context = CatalogContext(
        catalog=context.catalog,
        scope="project",
        profile=context.profile,
        project_root=context.project_root,
        include_global=True,
        project_found=context.project_found,
        effective_source=f"project+{_resolve_read_route(profile=profile, db_path=db_path, source_mode=source_mode).effective_source}",
    )
    return merged, merged_context


def _filter_entry_collection(
    entries: Sequence[CatalogEntry],
    *,
    kind: str | None = None,
    tags: Sequence[str] | None = None,
    field_filters: Mapping[str, object] | Sequence[tuple[str, object]] | None = None,
) -> list[CatalogEntry]:
    normalized_kind = _normalize_kind(kind)
    filters = _normalize_field_filters(field_filters)
    selected = list(entries)
    if normalized_kind is not None:
        selected = [entry for entry in selected if entry.kind == normalized_kind]
    selected = [
        entry
        for entry in selected
        if _matches_tags(entry, tags) and _matches_field_filters(entry, filters)
    ]
    return _sort_entries(selected)


def _search_entry_collection(
    entries: Sequence[CatalogEntry],
    query: str,
    *,
    kind: str | None = None,
    tags: Sequence[str] | None = None,
    field: str = "all",
    limit: int = 20,
    field_filters: Mapping[str, object] | Sequence[tuple[str, object]] | None = None,
) -> list[CatalogEntry]:
    text = str(query or "").strip()
    filtered = _filter_entry_collection(entries, kind=kind, tags=tags, field_filters=field_filters)
    if not text:
        return filtered[: max(0, int(limit))]
    catalog = Catalog(filtered)
    hits = catalog.search(
        text,
        kinds=(_normalize_kind(kind),) if _normalize_kind(kind) else None,
        tags=tuple(_normalize_strings(tags)) or None,
        fields=_normalize_field(field),
        limit=len(filtered) or max(20, int(limit)),
    )
    hydrated = _hydrate_entries(hits, catalog=catalog)
    ordered = _sort_entries(hydrated)
    return ordered[: max(0, int(limit))]


def _entry_values(entry: CatalogEntry, field_name: str) -> tuple[str, ...]:
    field = str(field_name or "").strip().lower()
    if not field:
        return ()
    if field == "key":
        return (entry.key,)
    if field in {"title", "name"}:
        return (entry.title,)
    if field == "kind":
        return (entry.kind,)
    if field == "import_path":
        return (entry.import_path,)
    if field == "module":
        return (entry.import_path.partition(":")[0].strip(),) if entry.import_path.strip() else ()
    if field == "symbol":
        symbol = entry.import_path.partition(":")[2].strip()
        return (symbol,) if symbol else ()
    if field == "summary":
        return (entry.summary,) if entry.summary else ()
    if field in {
        "tags",
        "companions",
        "context_requires",
        "context_provides",
        "context_mutates",
        "context_cache",
        "context_notes",
        "artifact_requires",
        "artifact_provides",
        "phase_in",
        "phase_out",
        "use_when",
        "minimal_wiring",
        "required_companions",
        "config_keys",
    }:
        return _normalize_strings(getattr(entry, field, ()))
    if field == "example_entry":
        return _normalize_strings(getattr(entry, "example_entry", ""))
    return ()


def _hydrate_entries(entries: Iterable[CatalogEntry], *, catalog: Catalog) -> list[CatalogEntry]:
    out: list[CatalogEntry] = []
    for entry in entries:
        hydrated = catalog.get(entry.key)
        out.append(hydrated if hydrated is not None else entry)
    return out


def _matches_tags(entry: CatalogEntry, tags: Sequence[str] | None) -> bool:
    expected = {value.lower() for value in _normalize_strings(tags)}
    if not expected:
        return True
    current = {value.lower() for value in entry.tags}
    return expected.issubset(current)


def _matches_field_filters(
    entry: CatalogEntry,
    field_filters: Mapping[str, tuple[str, ...]] | None,
) -> bool:
    if not field_filters:
        return True
    for field_name, expected_values in field_filters.items():
        expected = {value.lower() for value in expected_values}
        current = {value.lower() for value in _entry_values(entry, field_name)}
        if not current:
            return False
        if current.isdisjoint(expected):
            return False
    return True


def _sort_entries(entries: Iterable[CatalogEntry]) -> list[CatalogEntry]:
    kind_order = {
        "adapter": 0,
        "plugin": 1,
        "bias": 2,
        "representation": 3,
        "resource": 4,
        "backend": 5,
        "suite": 6,
        "tool": 7,
        "doc": 8,
        "example": 9,
    }
    return sorted(entries, key=lambda entry: (kind_order.get(entry.kind, 99), entry.key))


def _entry_payload(entry: CatalogEntry) -> dict[str, Any]:
    usage = build_usage_profile(entry)
    return {
        "key": entry.key,
        "title": entry.title,
        "kind": entry.kind,
        "import_path": entry.import_path,
        "module": entry.import_path.partition(":")[0].strip(),
        "symbol": entry.import_path.partition(":")[2].strip(),
        "tags": tuple(entry.tags),
        "summary": entry.summary,
        "companions": tuple(entry.companions),
        "context_requires": tuple(entry.context_requires),
        "context_provides": tuple(entry.context_provides),
        "context_mutates": tuple(entry.context_mutates),
        "context_cache": tuple(entry.context_cache),
        "context_notes": tuple(entry.context_notes),
        "artifact_requires": tuple(getattr(entry, "artifact_requires", ()) or ()),
        "artifact_provides": tuple(getattr(entry, "artifact_provides", ()) or ()),
        "phase_in": tuple(getattr(entry, "phase_in", ()) or ()),
        "phase_out": tuple(getattr(entry, "phase_out", ()) or ()),
        "use_when": tuple(usage.use_when),
        "minimal_wiring": tuple(usage.minimal_wiring),
        "required_companions": tuple(usage.required_companions),
        "config_keys": tuple(usage.config_keys),
        "example_entry": str(usage.example_entry or ""),
    }


def list_entries(
    *,
    profile: str | None = None,
    scope: str | None = None,
    project_path: str | Path | None = None,
    include_global: bool = False,
    kind: str | None = None,
    tags: Sequence[str] | None = None,
    limit: int | None = None,
    field_filters: Mapping[str, object] | Sequence[tuple[str, object]] | None = None,
    db_path: str | None = None,
    source_mode: str | None = None,
) -> list[CatalogEntry]:
    normalized_scope = _normalize_scope(scope)
    if normalized_scope == "framework":
        route = _resolve_read_route(profile=profile, db_path=db_path, source_mode=source_mode)
        if route.db_store is not None:
            ordered = route.db_store.list_catalog_entries(
                profile=route.profile,
                kind=kind,
                tags=tags,
                limit=limit,
                field_filters=field_filters,
            )
        else:
            context = _load_catalog_context(
                profile=profile,
                scope="framework",
                project_path=project_path,
                include_global=False,
            )
            entries = _hydrate_entries(context.catalog.list(kind=_normalize_kind(kind)), catalog=context.catalog)
            ordered = _filter_entry_collection(entries, kind=kind, tags=tags, field_filters=field_filters)
    else:
        entries, _context = _project_entries(
            profile=profile,
            project_path=project_path,
            include_global=include_global,
            db_path=db_path,
            source_mode=source_mode,
        )
        ordered = _filter_entry_collection(entries, kind=kind, tags=tags, field_filters=field_filters)
    if limit is None:
        return ordered
    return ordered[: max(0, int(limit))]


def search_entries(
    query: str,
    *,
    profile: str | None = None,
    scope: str | None = None,
    project_path: str | Path | None = None,
    include_global: bool = False,
    kind: str | None = None,
    tags: Sequence[str] | None = None,
    field: str = "all",
    limit: int = 20,
    field_filters: Mapping[str, object] | Sequence[tuple[str, object]] | None = None,
    db_path: str | None = None,
    source_mode: str | None = None,
) -> list[CatalogEntry]:
    text = str(query or "").strip()
    if not text:
        return list_entries(
            profile=profile,
            scope=scope,
            project_path=project_path,
            include_global=include_global,
            kind=kind,
            tags=tags,
            limit=limit,
            field_filters=field_filters,
            db_path=db_path,
            source_mode=source_mode,
        )
    normalized_scope = _normalize_scope(scope)
    if normalized_scope == "framework":
        route = _resolve_read_route(profile=profile, db_path=db_path, source_mode=source_mode)
        if route.db_store is not None:
            return route.db_store.search_catalog_entries(
                text,
                profile=route.profile,
                kind=kind,
                tags=tags,
                field=field,
                limit=limit,
                field_filters=field_filters,
            )
        context = _load_catalog_context(
            profile=profile,
            scope="framework",
            project_path=project_path,
            include_global=False,
        )
        entries = _hydrate_entries(context.catalog.list(), catalog=context.catalog)
        return _search_entry_collection(
            entries,
            text,
            kind=kind,
            tags=tags,
            field=field,
            limit=limit,
            field_filters=field_filters,
        )
    entries, _context = _project_entries(
        profile=profile,
        project_path=project_path,
        include_global=include_global,
        db_path=db_path,
        source_mode=source_mode,
    )
    return _search_entry_collection(
        entries,
        text,
        kind=kind,
        tags=tags,
        field=field,
        limit=limit,
        field_filters=field_filters,
    )


def show_entry(
    key: str,
    *,
    profile: str | None = None,
    scope: str | None = None,
    project_path: str | Path | None = None,
    include_global: bool = False,
    db_path: str | None = None,
    source_mode: str | None = None,
) -> CatalogEntry | None:
    normalized_key = str(key or "").strip()
    if not normalized_key:
        return None
    normalized_scope = _normalize_scope(scope)
    if normalized_scope == "framework":
        route = _resolve_read_route(profile=profile, db_path=db_path, source_mode=source_mode)
        if route.db_store is not None:
            return route.db_store.get_catalog_entry(normalized_key, profile=route.profile)
        context = _load_catalog_context(
            profile=profile,
            scope="framework",
            project_path=project_path,
            include_global=False,
        )
        return context.catalog.get(normalized_key)
    entries, _context = _project_entries(
        profile=profile,
        project_path=project_path,
        include_global=include_global,
        db_path=db_path,
        source_mode=source_mode,
    )
    for entry in entries:
        if entry.key == normalized_key:
            return entry
    return None


def catalog_source_info(
    *,
    profile: str | None = None,
    scope: str | None = None,
    project_path: str | Path | None = None,
    include_global: bool = False,
    db_path: str | None = None,
    source_mode: str | None = None,
) -> dict[str, Any]:
    normalized_scope = _normalize_scope(scope)
    route = _resolve_read_route(profile=profile, db_path=db_path, source_mode=source_mode)
    if normalized_scope == "project":
        context = _load_catalog_context(
            profile=profile,
            scope="project",
            project_path=project_path,
            include_global=False,
        )
        effective_source = f"project+{route.effective_source}" if include_global and context.project_found else context.effective_source
    else:
        context = _load_catalog_context(
            profile=profile,
            scope="framework",
            project_path=project_path,
            include_global=False,
        )
        effective_source = route.effective_source
    framework_info = _framework_source_info()
    info: dict[str, Any] = {
        "profile": context.profile,
        "scope": normalized_scope,
        "project_root": context.project_root,
        "project_found": context.project_found,
        "include_global": bool(include_global) if normalized_scope == "project" else False,
        "effective_source": effective_source,
        "source_mode": route.source_mode,
        "route_db_backend": route.db_backend,
        "explicit_db_path": bool(route.explicit_db_path),
        "db_error": route.db_error,
    }
    info.update(framework_info)
    info.update(catalog_db_config_info())
    return info


def catalog_summary(
    *,
    profile: str | None = None,
    scope: str | None = None,
    project_path: str | Path | None = None,
    include_global: bool = False,
    db_path: str | None = None,
    source_mode: str | None = None,
) -> dict[str, Any]:
    normalized_scope = _normalize_scope(scope)
    if normalized_scope == "framework":
        entries = list_entries(
            profile=profile,
            scope="framework",
            include_global=False,
            limit=None,
            db_path=db_path,
            source_mode=source_mode,
        )
        context = _load_catalog_context(profile=profile, scope="framework", project_path=project_path, include_global=False)
    else:
        entries, context = _project_entries(
            profile=profile,
            project_path=project_path,
            include_global=include_global,
            db_path=db_path,
            source_mode=source_mode,
        )
    by_kind = Counter(entry.kind for entry in entries)
    tags = sorted({tag for entry in entries for tag in entry.tags})
    return {
        "profile": context.profile,
        "scope": normalized_scope,
        "project_root": context.project_root,
        "project_found": context.project_found,
        "include_global": bool(include_global) if normalized_scope == "project" else False,
        "total": len(entries),
        "by_kind": dict(sorted(by_kind.items())),
        "unique_tags": len(tags),
    }


def catalog_schema(
    *,
    profile: str | None = None,
    scope: str | None = None,
    project_path: str | Path | None = None,
    include_global: bool = False,
    kind: str | None = None,
    db_path: str | None = None,
    source_mode: str | None = None,
) -> dict[str, Any]:
    normalized_scope = _normalize_scope(scope)
    normalized_kind = _normalize_kind(kind)
    if normalized_scope == "framework":
        context = _load_catalog_context(
            profile=profile,
            scope="framework",
            project_path=project_path,
            include_global=False,
        )
        entries = list_entries(
            profile=profile,
            scope="framework",
            include_global=False,
            kind=normalized_kind,
            limit=None,
            db_path=db_path,
            source_mode=source_mode,
        )
        kinds_entries = list_entries(
            profile=profile,
            scope="framework",
            include_global=False,
            limit=None,
            db_path=db_path,
            source_mode=source_mode,
        )
    else:
        all_project_entries, context = _project_entries(
            profile=profile,
            project_path=project_path,
            include_global=include_global,
            db_path=db_path,
            source_mode=source_mode,
        )
        entries = _filter_entry_collection(all_project_entries, kind=normalized_kind, field_filters=None)
        kinds_entries = all_project_entries
    fields = tuple(
        field_name
        for field_name in _CATALOG_FIELD_ORDER
        if any(_entry_values(entry, field_name) for entry in entries)
    )
    kinds = tuple(sorted({entry.kind for entry in kinds_entries}))
    return {
        "profile": context.profile,
        "scope": normalized_scope,
        "project_root": context.project_root,
        "project_found": context.project_found,
        "include_global": bool(include_global) if normalized_scope == "project" else False,
        "kind": normalized_kind,
        "kinds": kinds,
        "fields": fields,
        "field_groups": _FIELD_GROUPS,
        "search_fields": ("all", "name", "tag", "context", "usage"),
        "counts": {"entries": len(entries)},
    }


def field_values(
    field_name: str,
    *,
    profile: str | None = None,
    scope: str | None = None,
    project_path: str | Path | None = None,
    include_global: bool = False,
    kind: str | None = None,
    query: str = "",
    search_field: str = "all",
    limit: int = 100,
    field_filters: Mapping[str, object] | Sequence[tuple[str, object]] | None = None,
    db_path: str | None = None,
    source_mode: str | None = None,
) -> tuple[dict[str, Any], ...]:
    normalized_scope = _normalize_scope(scope)
    if normalized_scope == "framework":
        route = _resolve_read_route(profile=profile, db_path=db_path, source_mode=source_mode)
        if route.db_store is not None:
            return tuple(
                route.db_store.field_values(
                    field_name,
                    profile=route.profile,
                    kind=kind,
                    query=query,
                    search_field=search_field,
                    limit=limit,
                    field_filters=field_filters,
                )
            )
    context = _load_catalog_context(
        profile=profile,
        scope=scope,
        project_path=project_path,
        include_global=include_global,
    )
    entries = (
        search_entries(
            query,
            profile=profile,
            scope=scope,
            project_path=project_path,
            include_global=include_global,
            kind=kind,
            field=search_field,
            limit=len(context.catalog.list(kind=_normalize_kind(kind))) or 200,
            field_filters=field_filters,
            db_path=db_path,
            source_mode=source_mode,
        )
        if str(query or "").strip()
        else list_entries(
            profile=profile,
            scope=scope,
            project_path=project_path,
            include_global=include_global,
            kind=kind,
            limit=None,
            field_filters=field_filters,
            db_path=db_path,
            source_mode=source_mode,
        )
    )
    counter: Counter[str] = Counter()
    for entry in entries:
        for value in _entry_values(entry, field_name):
            counter[value] += 1
    rows = sorted(counter.items(), key=lambda item: (-item[1], item[0].lower()))
    return tuple({"value": value, "count": count} for value, count in rows[: max(0, int(limit))])


def catalog_facets(
    *,
    profile: str | None = None,
    scope: str | None = None,
    project_path: str | Path | None = None,
    include_global: bool = False,
    kind: str | None = None,
    query: str = "",
    search_field: str = "all",
    field_filters: Mapping[str, object] | Sequence[tuple[str, object]] | None = None,
    fields: Sequence[str] | None = None,
    limit_per_field: int = 25,
    db_path: str | None = None,
    source_mode: str | None = None,
) -> dict[str, Any]:
    normalized_scope = _normalize_scope(scope)
    normalized_kind = _normalize_kind(kind)
    normalized_filters = _normalize_field_filters(field_filters)
    if normalized_scope == "framework":
        route = _resolve_read_route(profile=profile, db_path=db_path, source_mode=source_mode)
        if route.db_store is not None:
            facet_fields = tuple(fields or _DEFAULT_FACET_FIELDS.get(normalized_kind or "", ("tags", "companions")))
            payload = route.db_store.facet_rows(
                profile=route.profile,
                kind=normalized_kind,
                query=query,
                search_field=search_field,
                field_filters=normalized_filters,
                fields=facet_fields,
                limit_per_field=limit_per_field,
            )
            total = len(
                search_entries(
                    query,
                    profile=profile,
                    scope="framework",
                    include_global=False,
                    kind=normalized_kind,
                    field=search_field,
                    limit=10_000,
                    field_filters=normalized_filters,
                    db_path=db_path,
                    source_mode=source_mode,
                )
                if str(query or "").strip()
                else list_entries(
                    profile=profile,
                    scope="framework",
                    include_global=False,
                    kind=normalized_kind,
                    limit=None,
                    field_filters=normalized_filters,
                    db_path=db_path,
                    source_mode=source_mode,
                )
            )
            return {
                "profile": route.profile,
                "scope": "framework",
                "project_root": None,
                "project_found": True,
                "include_global": False,
                "kind": normalized_kind,
                "query": str(query or ""),
                "search_field": _normalize_field(search_field),
                "field_filters": normalized_filters,
                "total": total,
                "facets": payload,
            }
    context = _load_catalog_context(
        profile=profile,
        scope=scope,
        project_path=project_path,
        include_global=include_global,
    )
    if str(query or "").strip():
        entries = search_entries(
            query,
            profile=profile,
            scope=scope,
            project_path=project_path,
            include_global=include_global,
            kind=normalized_kind,
            field=search_field,
            limit=len(context.catalog.list(kind=normalized_kind)) or 200,
            field_filters=normalized_filters,
            db_path=db_path,
            source_mode=source_mode,
        )
    else:
        entries = list_entries(
            profile=profile,
            scope=scope,
            project_path=project_path,
            include_global=include_global,
            kind=normalized_kind,
            limit=None,
            field_filters=normalized_filters,
            db_path=db_path,
            source_mode=source_mode,
        )
    facet_fields = tuple(fields or _DEFAULT_FACET_FIELDS.get(normalized_kind or "", ("tags", "companions")))
    payload: dict[str, list[dict[str, Any]]] = {}
    for field_name in facet_fields:
        counter: Counter[str] = Counter()
        for entry in entries:
            for value in _entry_values(entry, field_name):
                counter[value] += 1
        rows = sorted(counter.items(), key=lambda item: (-item[1], item[0].lower()))
        payload[str(field_name)] = [
            {"value": value, "count": count}
            for value, count in rows[: max(0, int(limit_per_field))]
        ]
    return {
        "profile": context.profile,
        "scope": context.scope,
        "project_root": context.project_root,
        "project_found": context.project_found,
        "include_global": context.include_global,
        "kind": normalized_kind,
        "query": str(query or ""),
        "search_field": _normalize_field(search_field),
        "field_filters": normalized_filters,
        "total": len(entries),
        "facets": payload,
    }


def catalog_neighbors(
    key: str,
    *,
    profile: str | None = None,
    scope: str | None = None,
    project_path: str | Path | None = None,
    include_global: bool = False,
    db_path: str | None = None,
    source_mode: str | None = None,
) -> dict[str, Any] | None:
    normalized_scope = _normalize_scope(scope)
    if normalized_scope == "framework":
        route = _resolve_read_route(profile=profile, db_path=db_path, source_mode=source_mode)
        if route.db_store is not None:
            payload = route.db_store.neighbor_payload(key, profile=route.profile)
            if payload is None:
                return None
            payload.update(
                {
                    "scope": "framework",
                    "project_root": None,
                    "project_found": True,
                    "include_global": False,
                }
            )
            return payload
    context = _load_catalog_context(
        profile=profile,
        scope=scope,
        project_path=project_path,
        include_global=include_global,
    )
    entry = context.catalog.get(str(key or "").strip())
    if entry is None:
        return None
    companions: list[dict[str, Any]] = []
    missing_companions: list[str] = []
    for companion_key in entry.companions:
        companion = context.catalog.get(companion_key)
        if companion is None:
            missing_companions.append(companion_key)
            continue
        companions.append(_entry_payload(companion))

    catalog_entries = list_entries(
        profile=profile,
        scope=scope,
        project_path=project_path,
        include_global=include_global,
        limit=None,
        db_path=db_path,
        source_mode=source_mode,
    )
    linked_by = [
        _entry_payload(candidate)
        for candidate in catalog_entries
        if entry.key in candidate.companions and candidate.key != entry.key
    ]
    all_candidates = [
        candidate
        for candidate in catalog_entries
        if candidate.key != entry.key
    ]
    contract_sections = build_contract_neighbor_sections(entry, candidates=all_candidates)
    return {
        "key": entry.key,
        "scope": context.scope,
        "project_root": context.project_root,
        "companions": companions,
        "missing_companions": tuple(missing_companions),
        "linked_by": linked_by,
        **contract_sections,
    }


def catalog_ui_snapshot(
    *,
    profile: str | None = None,
    scope: str | None = None,
    project_path: str | Path | None = None,
    include_global: bool = False,
    kind: str | None = None,
    query: str = "",
    search_field: str = "all",
    field_filters: Mapping[str, object] | Sequence[tuple[str, object]] | None = None,
    limit: int = 50,
    selected_key: str | None = None,
    db_path: str | None = None,
    source_mode: str | None = None,
) -> dict[str, Any]:
    items = (
        search_entries(
            query,
            profile=profile,
            scope=scope,
            project_path=project_path,
            include_global=include_global,
            kind=kind,
            field=search_field,
            limit=limit,
            field_filters=field_filters,
            db_path=db_path,
            source_mode=source_mode,
        )
        if str(query or "").strip()
        else list_entries(
            profile=profile,
            scope=scope,
            project_path=project_path,
            include_global=include_global,
            kind=kind,
            limit=limit,
            field_filters=field_filters,
            db_path=db_path,
            source_mode=source_mode,
        )
    )
    selected = (
        show_entry(
            selected_key,
            profile=profile,
            scope=scope,
            project_path=project_path,
            include_global=include_global,
            db_path=db_path,
            source_mode=source_mode,
        )
        if selected_key
        else None
    )
    return {
        "source": catalog_source_info(
            profile=profile,
            scope=scope,
            project_path=project_path,
            include_global=include_global,
            db_path=db_path,
            source_mode=source_mode,
        ),
        "summary": catalog_summary(
            profile=profile,
            scope=scope,
            project_path=project_path,
            include_global=include_global,
            db_path=db_path,
            source_mode=source_mode,
        ),
        "schema": catalog_schema(
            profile=profile,
            scope=scope,
            project_path=project_path,
            include_global=include_global,
            kind=kind,
            db_path=db_path,
            source_mode=source_mode,
        ),
        "facets": catalog_facets(
            profile=profile,
            scope=scope,
            project_path=project_path,
            include_global=include_global,
            kind=kind,
            query=query,
            search_field=search_field,
            field_filters=field_filters,
            db_path=db_path,
            source_mode=source_mode,
        ),
        "items": [_entry_payload(entry) for entry in items],
        "selected": _entry_payload(selected) if selected is not None else None,
        "neighbors": (
            catalog_neighbors(
                selected.key,
                profile=profile,
                scope=scope,
                project_path=project_path,
                include_global=include_global,
                db_path=db_path,
                source_mode=source_mode,
            )
            if selected is not None
            else None
        ),
    }
