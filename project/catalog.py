# -*- coding: utf-8 -*-
"""Project-local catalog utilities (non-global, opt-in)."""

from __future__ import annotations

from dataclasses import asdict, replace
from pathlib import Path
from typing import Iterable, List, Optional

from ..catalog import get_catalog
from ..catalog.registry import Catalog, CatalogEntry
from ..catalog.usage import enrich_context_contracts, enrich_usage_contracts
from blackbase.project import find_catalog_scope, load_scaffold_catalog_entries
from blackbase.project.runtime import project_import_context


def find_project_root(start: Path | str) -> Optional[Path]:
    """Find the nearest formal Project or Case catalog scope."""
    scope = find_catalog_scope(start)
    return None if scope is None else scope.root


def _normalize_project_entries(entries: Iterable[CatalogEntry]) -> List[CatalogEntry]:
    out: List[CatalogEntry] = []
    for e in entries:
        key = e.key if e.key.startswith("project.") else f"project.{e.key}"
        out.append(replace(e, key=key))
    return out


def _load_project_toml_entries(project_root: Path) -> List[CatalogEntry]:
    """
    Load project-local entries from:
    - <project_root>/catalog/entries/*.toml

    This is the only project-local catalog source in the formal scaffold.
    """
    entries = load_scaffold_catalog_entries(project_root)
    return [CatalogEntry(**entry.as_dict()) for entry in entries]


def load_project_entries(project_root: Path | str) -> List[CatalogEntry]:
    """Load entries from the formal project-local TOML catalog."""
    root = Path(project_root).resolve()
    entries = _normalize_project_entries(_load_project_toml_entries(root))
    if not entries:
        raise FileNotFoundError(f"No project catalog entries found under: {root}")
    return entries


def load_project_catalog(
    project_root: Path | str,
    *,
    include_global: bool = False,
    profile: str | None = None,
) -> Catalog:
    """Build Catalog for a project; optionally merge global catalog."""
    root = Path(project_root).resolve()
    with project_import_context(root):
        local_entries = enrich_context_contracts(
            load_project_entries(root),
            kinds=("plugin", "adapter", "bias", "representation"),
        )
        local_entries = enrich_usage_contracts(local_entries)
        if not include_global:
            return Catalog(local_entries)

        global_entries = get_catalog(profile=profile).list()
        local_keys = {e.key for e in local_entries}
        merged = list(local_entries) + [e for e in global_entries if e.key not in local_keys]
        merged = enrich_context_contracts(
            merged,
            kinds=("plugin", "adapter", "bias", "representation"),
        )
        return Catalog(enrich_usage_contracts(merged))


def export_project_entries(entries: Iterable[CatalogEntry]) -> List[dict]:
    """Serialize entries for debugging or docs."""
    out = []
    for e in entries:
        if isinstance(e, CatalogEntry):
            out.append(asdict(e))
    return out
