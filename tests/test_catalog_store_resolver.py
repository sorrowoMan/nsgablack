from __future__ import annotations


def test_catalog_store_prefers_postgres_when_both_backends_are_enabled(monkeypatch):
    import nsgablack.catalog.store as store_mod

    class _FakePostgresStore:
        backend = "postgresql"

        def __init__(self, url=None, readonly=None):
            self.url = url
            self.readonly = readonly

    class _FakeMySQLStore:
        backend = "mysql"

        def __init__(self, url=None, readonly=None):
            self.url = url
            self.readonly = readonly

    monkeypatch.delenv("NSGABLACK_CATALOG_DB_URL", raising=False)
    monkeypatch.setattr(store_mod, "postgres_config_enabled", lambda: True)
    monkeypatch.setattr(store_mod, "mysql_config_enabled", lambda: True)
    monkeypatch.setattr(store_mod, "PostgresCatalogStore", _FakePostgresStore)
    monkeypatch.setattr(store_mod, "MySQLCatalogStore", _FakeMySQLStore)

    store = store_mod.resolve_catalog_store(readonly=True)

    assert isinstance(store, _FakePostgresStore)
    assert store_mod.catalog_db_config_backend() == "postgresql"


def test_framework_core_sql_filter_binds_every_placeholder_once() -> None:
    from nsgablack.catalog.store.mysql import _profile_sql_filters

    clause, params = _profile_sql_filters("framework-core")

    assert clause.count("%s") == len(params)
    assert params[:2] == ["example", "doc"]
