# -*- coding: utf-8 -*-
"""Project-local catalog utilities (non-global, opt-in)."""

from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import Iterable, List, Optional, Sequence, Tuple
import importlib.util
import sys

from ..catalog import get_catalog
from ..catalog.registry import Catalog, CatalogEntry
from ..catalog.usage import enrich_usage_contracts


def find_project_root(start: Path | str) -> Optional[Path]:
    """Find nearest folder containing project_registry.py."""
    p = Path(start).resolve()
    if p.is_file():
        p = p.parent
    for cur in [p] + list(p.parents):
        if (cur / "project_registry.py").is_file():
            return cur
    return None


def _load_registry_module(registry_path: Path):
    spec = importlib.util.spec_from_file_location("nsgablack_project_registry", registry_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot import project registry: {registry_path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[call-arg]
    return mod


def _coerce_entry(item) -> CatalogEntry:
    if isinstance(item, CatalogEntry):
        return item
    if isinstance(item, dict):
        return CatalogEntry(**item)
    raise TypeError(f"Invalid catalog entry type: {type(item)!r}")


def _normalize_project_entries(entries: Iterable[CatalogEntry]) -> List[CatalogEntry]:
    out: List[CatalogEntry] = []
    for e in entries:
        key = e.key
        if not key.startswith("project."):
            key = f"project.{key}"
        out.append(
            CatalogEntry(
                key=key,
                title=e.title,
                kind=e.kind,
                import_path=e.import_path,
                tags=tuple(e.tags or ()),
                summary=e.summary or "",
                companions=tuple(e.companions or ()),
                context_requires=tuple(getattr(e, "context_requires", ()) or ()),
                context_provides=tuple(getattr(e, "context_provides", ()) or ()),
                context_mutates=tuple(getattr(e, "context_mutates", ()) or ()),
                context_cache=tuple(getattr(e, "context_cache", ()) or ()),
                context_notes=tuple(getattr(e, "context_notes", ()) or ()),
                use_when=tuple(getattr(e, "use_when", ()) or ()),
                minimal_wiring=tuple(getattr(e, "minimal_wiring", ()) or ()),
                required_companions=tuple(getattr(e, "required_companions", ()) or ()),
                config_keys=tuple(getattr(e, "config_keys", ()) or ()),
                example_entry=str(getattr(e, "example_entry", "") or ""),
            )
        )
    return out


def load_project_entries(project_root: Path | str) -> List[CatalogEntry]:
    """Load entries from project_registry.py."""
    root = Path(project_root).resolve()
    registry_path = root / "project_registry.py"
    if not registry_path.is_file():
        raise FileNotFoundError(f"project_registry.py not found under: {root}")

    # Ensure local project modules are importable.
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

    mod = _load_registry_module(registry_path)

    raw_entries: Sequence = []
    if hasattr(mod, "get_project_entries"):
        raw_entries = mod.get_project_entries()
    elif hasattr(mod, "PROJECT_CATALOG_ENTRIES"):
        raw_entries = getattr(mod, "PROJECT_CATALOG_ENTRIES")
    elif hasattr(mod, "CATALOG_ENTRIES"):
        raw_entries = getattr(mod, "CATALOG_ENTRIES")
    else:
        raise AttributeError("project_registry.py must define get_project_entries() or PROJECT_CATALOG_ENTRIES")

    entries = [_coerce_entry(item) for item in list(raw_entries)]
    return _normalize_project_entries(entries)


def load_project_catalog(project_root: Path | str, *, include_global: bool = False) -> Catalog:
    """Build Catalog for a project; optionally merge global catalog."""
    local_entries = enrich_usage_contracts(load_project_entries(project_root))
    if not include_global:
        return Catalog(local_entries)

    global_entries = get_catalog().list()
    local_keys = {e.key for e in local_entries}
    merged = list(local_entries) + [e for e in global_entries if e.key not in local_keys]
    return Catalog(enrich_usage_contracts(merged))


def export_project_entries(entries: Iterable[CatalogEntry]) -> List[dict]:
    """Serialize entries for debugging or docs."""
    out = []
    for e in entries:
        if isinstance(e, CatalogEntry):
            out.append(asdict(e))
    return out
