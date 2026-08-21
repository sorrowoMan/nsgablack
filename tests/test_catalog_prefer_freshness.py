from __future__ import annotations

from nsgablack.catalog import facade
from nsgablack.catalog import sync as sync_mod
from nsgablack.catalog.fingerprint import catalog_entries_digest
from nsgablack.catalog.registry import CatalogEntry, get_source_catalog


class _DigestStore:
    backend = "postgresql"

    def __init__(self, digest: str | None) -> None:
        self.digest = digest
        self.list_calls = 0

    def has_profile(self, *, profile: str = "default") -> bool:
        return True

    def profile_source_digest(self, *, profile: str = "default") -> str | None:
        return self.digest

    def list_catalog_entries(self, **kwargs):
        self.list_calls += 1
        return [
            CatalogEntry(
                key="example.retired",
                title="retired",
                kind="example",
                import_path="examples.retired:main",
            )
        ]


class _CaptureSyncStore:
    def __init__(self, backend: str) -> None:
        self.backend = backend
        self.bundle = None
        self.profile = None

    def sync_bundle(self, bundle, *, profile: str = "default") -> None:
        self.bundle = bundle
        self.profile = profile


def _configure_store(monkeypatch, store: _DigestStore, *, mode: str = "prefer") -> None:
    monkeypatch.setattr(facade, "catalog_db_config_enabled", lambda: True)
    monkeypatch.setattr(facade, "catalog_db_config_mode", lambda: mode)
    monkeypatch.setattr(facade, "resolve_catalog_store", lambda **kwargs: store)
    monkeypatch.setattr(facade, "catalog_db_config_info", lambda: {})


def test_prefer_mode_rejects_profile_without_current_source_fingerprint(monkeypatch) -> None:
    store = _DigestStore(None)
    _configure_store(monkeypatch, store)

    entries = facade.list_entries(profile="default", kind="example", source_mode="prefer")
    info = facade.catalog_source_info(profile="default", source_mode="prefer")

    assert entries
    assert all(entry.key != "example.retired" for entry in entries)
    assert info["effective_source"] == "registry"
    assert info["db_stale"] is True
    assert "no source fingerprint" in str(info["db_stale_reason"])


def test_prefer_mode_accepts_matching_materialized_profile(monkeypatch) -> None:
    source = get_source_catalog(profile="default").list()
    digest = catalog_entries_digest(source)
    store = _DigestStore(digest)
    _configure_store(monkeypatch, store)

    route = facade._resolve_read_route(profile="default", source_mode="prefer")

    assert route.db_store is store
    assert route.effective_source == "postgresql"
    assert route.db_stale is False


def test_only_mode_keeps_explicit_database_authority_without_freshness_gate(monkeypatch) -> None:
    store = _DigestStore("stale")
    _configure_store(monkeypatch, store, mode="only")

    entries = facade.list_entries(profile="default", kind="example", source_mode="only")

    assert [entry.key for entry in entries] == ["example.retired"]


def test_registry_search_prefers_key_segment_prefix_over_cross_word_substring() -> None:
    entries = facade.search_entries(
        "ns",
        profile="framework-core",
        kind="adapter",
        source_mode="off",
    )

    assert [entry.key for entry in entries[:2]] == ["adapter.nsga2", "adapter.nsga3"]


def test_postgres_materialization_fingerprints_the_requested_profile(monkeypatch) -> None:
    store = _CaptureSyncStore("postgresql")
    monkeypatch.setattr(sync_mod, "resolve_catalog_store", lambda **kwargs: store)

    sync_mod.materialize_catalog_to_db(profile="framework-core", db_url="postgresql://test")

    assert store.profile == "framework-core"
    assert store.bundle is not None
    assert store.bundle.source_digest == catalog_entries_digest(
        get_source_catalog(profile="framework-core").list()
    )
    assert not any(component.kind in {"doc", "example"} for component in store.bundle.components)


def test_mysql_materialization_keeps_default_union_for_query_time_profiles(monkeypatch) -> None:
    store = _CaptureSyncStore("mysql")
    monkeypatch.setattr(sync_mod, "resolve_catalog_store", lambda **kwargs: store)

    sync_mod.materialize_catalog_to_db(profile="framework-core", db_url="mysql://test")

    assert store.profile == "framework-core"
    assert store.bundle is not None
    assert any(component.kind == "example" for component in store.bundle.components)
