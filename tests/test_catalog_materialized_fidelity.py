"""The complete source must survive SQL publication without semantic edits."""
from __future__ import annotations

import ast
from dataclasses import replace

import pytest

from nsgablack.catalog.fingerprint import catalog_entries_digest
from nsgablack.catalog.registry import get_source_catalog, apply_catalog_profile_entry
from nsgablack.catalog.store.mysql import MySQLCatalogStore
from nsgablack.catalog.store.postgres import PostgresCatalogStore
from nsgablack.catalog.sync import build_catalog_bundle, _build_usage_contract
from tests.test_catalog_guidance_storage import LocalConnection, materialize_legacy


@pytest.fixture(scope="module")
def published_sources():
    sources = {profile: get_source_catalog(refresh=True, profile=profile).list()
               for profile in ("default", "framework-core")}
    bundles = {profile: build_catalog_bundle(profile=profile, runtime=False, entries=entries)
               for profile, entries in sources.items()}
    return sources, bundles


@pytest.mark.parametrize("backend", ["mysql", "postgres-legacy", "postgres-surface"])
@pytest.mark.parametrize("profile", ["default", "framework-core"])
def test_all_source_entries_keep_exact_sql_semantic_fingerprint(published_sources, backend, profile):
    sources, bundles = published_sources
    store = MySQLCatalogStore("mysql://local/local") if backend == "mysql" else PostgresCatalogStore("postgresql://local/local")
    connection = LocalConnection(mapping_rows=backend != "mysql")
    try:
        if backend == "postgres-surface":
            store._materialize_surface_catalog(connection, bundles[profile], profile=profile)
            restored = store._surface_entries_from_query(connection, profile=profile)
        else:
            materialize_legacy(store, connection, bundles["default"])
            restored = store._catalog_entries_from_query(connection, profile=profile)
        assert sorted(entry.key for entry in restored) == sorted(entry.key for entry in sources[profile])
        assert catalog_entries_digest(restored) == catalog_entries_digest(sources[profile])
        for entry in restored:
            if entry.key in {"adapter.astar", "adapter.moa_star"}:
                ast.parse("\n".join(entry.minimal_wiring))
    finally:
        connection.native.close()


def test_core_is_only_the_final_profile_of_the_complete_enriched_source(published_sources):
    sources, _ = published_sources
    expected = [filtered for entry in sources["default"]
                if (filtered := apply_catalog_profile_entry(entry, profile="framework-core")) is not None]
    assert catalog_entries_digest(sources["framework-core"]) == catalog_entries_digest(expected)
    for entry in sources["framework-core"]:
        assert entry.kind not in {"example", "doc"}
        assert "examples/" not in entry.import_path.replace("\\", "/").lower()
        assert "examples/" not in entry.example_entry.replace("\\", "/").lower()


def test_usage_publication_does_not_reinfer_stripped_examples_or_normalize_code(published_sources):
    sources, _ = published_sources
    original = next(entry for entry in sources["default"] if entry.key == "adapter.astar")
    source = replace(original, example_entry="", minimal_wiring=("def neighbors(state, context):", "", "    return [state]"))
    published = _build_usage_contract(source)
    assert published.example_entry == ""
    assert published.minimal_wiring == source.minimal_wiring
    ast.parse("\n".join(published.minimal_wiring))
