"""Read-only Catalog queries must work with SELECT privileges alone."""
from __future__ import annotations

import sqlite3

import pytest

from nsgablack.catalog.store import mysql, postgres
from nsgablack.catalog.store.mysql import MySQLCatalogStore
from nsgablack.catalog.store.postgres import PostgresCatalogStore
from tests.test_catalog_guidance_storage import LocalConnection, bundle, materialize_legacy


@pytest.fixture(params=("mysql", "postgres"))
def published_catalog(request, monkeypatch):
    is_mysql = request.param == "mysql"
    connection = LocalConnection(mapping_rows=not is_mysql)
    # SQLite normally interprets an unknown double-quoted column as a string;
    # disable that compatibility so old PostgreSQL schemas fail as PostgreSQL does.
    if hasattr(connection.native, "setconfig"):
        connection.native.setconfig(sqlite3.SQLITE_DBCONFIG_DQS_DML, False)
    connection.native.executescript("""
CREATE TABLE catalog_schema_migrations (version INTEGER);
CREATE TABLE catalog_param_contract (component_id INTEGER, name TEXT, type TEXT,
 default_value TEXT, required INTEGER, description TEXT, source TEXT, order_index INTEGER);
CREATE TABLE catalog_method_contract (component_id INTEGER, name TEXT, required INTEGER,
 implemented INTEGER, signature TEXT, origin TEXT);
CREATE TABLE catalog_health (component_id INTEGER, import_ok INTEGER, context_ok INTEGER,
 methods_ok INTEGER, params_ok INTEGER, issues_json TEXT, last_checked_at TEXT);
CREATE TABLE catalog_api_index (profile TEXT, module_path TEXT, class_name TEXT,
 method_name TEXT, purpose TEXT, usage TEXT, lineno INTEGER);
CREATE TABLE catalog_api_index_meta (profile TEXT, file_count INTEGER,
 component_count INTEGER, method_count INTEGER, updated_at TEXT);
CREATE TABLE catalog_api_doc (profile TEXT, module_path TEXT, class_name TEXT,
 method_name TEXT, params_json TEXT, boundaries TEXT, side_effects TEXT,
 lifecycle TEXT, auto_fields_json TEXT, notes TEXT);
""")
    url = "mysql://reader@unused.invalid/catalog" if is_mysql else "postgresql://reader@unused.invalid/catalog"
    writer = MySQLCatalogStore(url) if is_mysql else PostgresCatalogStore(url)
    if is_mysql:
        materialize_legacy(writer, connection, bundle())
    else:
        writer._materialize_surface_catalog(connection, bundle(), profile="default")
    connection.native.commit()
    connection.statements.clear()
    store = MySQLCatalogStore(url, readonly=True) if is_mysql else PostgresCatalogStore(url, readonly=True)
    monkeypatch.setattr(mysql if is_mysql else postgres,
                        "_connect_mysql" if is_mysql else "_connect_postgres", lambda config: connection)
    yield store, connection
    connection.native.close()


def forbid_writes(connection):
    def commit_forbidden():
        raise AssertionError("Read-only Catalog attempted commit")

    connection.commit = commit_forbidden
    forbidden = {sqlite3.SQLITE_INSERT, sqlite3.SQLITE_UPDATE, sqlite3.SQLITE_DELETE,
                 sqlite3.SQLITE_CREATE_TABLE, sqlite3.SQLITE_ALTER_TABLE,
                 sqlite3.SQLITE_CREATE_INDEX, sqlite3.SQLITE_DROP_TABLE,
                 sqlite3.SQLITE_TRANSACTION, sqlite3.SQLITE_SAVEPOINT}
    connection.native.set_authorizer(lambda action, *unused:
                                    sqlite3.SQLITE_DENY if action in forbidden else sqlite3.SQLITE_OK)


def test_published_catalog_reads_with_select_only_privileges(published_catalog):
    store, connection = published_catalog
    forbid_writes(connection)
    assert [entry.key for entry in store.list_catalog_entries()] == ["tool.example"]
    assert [entry.key for entry in store.search_catalog_entries("投影池")] == ["tool.example"]
    entry = store.get_catalog_entry("tool.example")
    assert entry.contract["catalog"]["role"] == "pool-operation"
    assert store.field_values("role") == [{"value": "pool-operation", "count": 1}]
    if isinstance(store, PostgresCatalogStore):
        assert store.has_profile(profile="default")
        assert store.profile_source_digest(profile="default") == bundle().source_digest
    assert connection.statements
    assert all(sql.lstrip().upper().startswith("SELECT") for sql, _ in connection.statements)


def test_missing_table_fails_closed_without_creating_it(published_catalog):
    store, connection = published_catalog
    table = "catalog_field_value" if isinstance(store, MySQLCatalogStore) else "catalog_scalars"
    connection.native.execute(f"DROP TABLE {table}")
    connection.native.commit()
    forbid_writes(connection)
    with pytest.raises(RuntimeError, match=f"unavailable or outdated at {table}.*writable account"):
        store.list_catalog_entries()
    assert connection.native.execute("SELECT name FROM sqlite_master WHERE name = ?", (table,)).fetchone() is None


def test_outdated_columns_fail_closed_without_migrating(published_catalog):
    store, connection = published_catalog
    if isinstance(store, PostgresCatalogStore) and not hasattr(connection.native, "setconfig"):
        pytest.skip("This SQLite version cannot disable legacy double-quoted string literals")
    table, column = (("catalog_component", "contract_json") if isinstance(store, MySQLCatalogStore)
                     else ("catalog_entries", "fields_json"))
    connection.native.execute(f"ALTER TABLE {table} DROP COLUMN {column}")
    connection.native.commit()
    forbid_writes(connection)
    with pytest.raises(RuntimeError, match=f"unavailable or outdated at {table}.*writable account"):
        store.list_catalog_entries()


@pytest.mark.parametrize("backend", ("mysql", "postgres"))
def test_writer_keeps_existing_migration_path(backend, monkeypatch):
    store = (MySQLCatalogStore("mysql://unused.invalid/catalog", readonly=False) if backend == "mysql"
             else PostgresCatalogStore("postgresql://unused.invalid/catalog", readonly=False))
    calls = []
    monkeypatch.setattr(store, "_apply_migrations", lambda conn: calls.append("migrations"))
    monkeypatch.setattr(store, "_ensure_field_value_index", lambda conn: calls.append("index"))
    if backend == "postgres":
        monkeypatch.setattr(store, "_ensure_surface_tables", lambda conn: calls.append("surface"))
        monkeypatch.setattr(store, "_legacy_support_retired", lambda conn: False)
        monkeypatch.setattr(store, "_ensure_field_value_table", lambda conn: calls.append("field_table"))
    store._ensure_schema(object())
    assert calls == (["migrations", "index"] if backend == "mysql"
                     else ["migrations", "surface", "field_table", "index"])
