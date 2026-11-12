"""Local SQL round trips; these tests never open a configured database."""
from __future__ import annotations

import json
import sqlite3
from dataclasses import replace
from types import MappingProxyType

import pytest

from nsgablack.catalog.contracts import CatalogBundle
from nsgablack.catalog.fingerprint import CATALOG_SOURCE_SCHEMA, catalog_entries_digest
from nsgablack.catalog.guidance import guidance_payload
from nsgablack.catalog.registry import CatalogEntry
from nsgablack.catalog import sync as sync_module
from nsgablack.catalog.store.mysql import MySQLCatalogStore
from nsgablack.catalog.store.postgres import PostgresCatalogStore


class LocalCursor:
    """Run common query SQL locally, adapting driver placeholders and upserts."""
    def __init__(self, connection):
        self.connection = connection
        self.cursor = connection.native.cursor()

    def execute(self, sql, params=()):
        self.connection.statements.append((sql, tuple(params or ())))
        if "ON DUPLICATE KEY UPDATE" in sql:
            # Round-trip fixtures insert unique keys; MySQL's upsert tail is
            # separately asserted below rather than imitated by this adapter.
            sql = sql.split("ON DUPLICATE KEY UPDATE", 1)[0]
        if "= ANY(%s)" in sql:
            values, = params
            sql = sql.replace("= ANY(%s)", "IN (" + ", ".join("%s" for _ in values) + ")")
            params = tuple(values)
        return self.cursor.execute(sql.replace("%s", "?"), tuple(params or ()))

    def executemany(self, sql, rows):
        self.connection.statements.append((sql, tuple(rows)))
        return self.cursor.executemany(sql.replace("%s", "?"), rows)

    def fetchall(self):
        rows = self.cursor.fetchall()
        if not self.connection.mapping_rows:
            return rows
        names = [column[0] for column in self.cursor.description]
        return [dict(zip(names, row)) for row in rows]

    def fetchone(self):
        row = self.cursor.fetchone()
        if row is None or not self.connection.mapping_rows:
            return row
        return dict(zip((column[0] for column in self.cursor.description), row))

    def close(self):
        self.cursor.close()


class LocalConnection:
    def __init__(self, *, mapping_rows=False):
        self.native = sqlite3.connect(":memory:")
        self.mapping_rows = mapping_rows
        self.statements = []
        self.native.executescript("""
CREATE TABLE catalog_component (
 id INTEGER PRIMARY KEY AUTOINCREMENT, key TEXT UNIQUE, kind TEXT, title TEXT,
 import_path TEXT, summary TEXT, tags TEXT, companions_json TEXT,
 source_scope TEXT, source_hash TEXT, contract_json TEXT, metadata_json TEXT, last_sync_at TEXT);
CREATE TABLE catalog_context_contract (
 component_id INTEGER PRIMARY KEY, requires_json TEXT, provides_json TEXT,
 mutates_json TEXT, cache_json TEXT, notes_json TEXT, artifact_requires_json TEXT,
 artifact_provides_json TEXT, phase_in_json TEXT, phase_out_json TEXT);
CREATE TABLE catalog_usage_contract (
 component_id INTEGER PRIMARY KEY, use_when_json TEXT, minimal_wiring_json TEXT,
 required_companions_json TEXT, config_keys_json TEXT, example_entry TEXT);
CREATE TABLE catalog_field_value (
 component_id INTEGER, field_scope TEXT, field_name TEXT, field_value TEXT, field_value_norm TEXT);
CREATE TABLE catalog_profiles (
 profile TEXT PRIMARY KEY, built_at_utc TEXT, total INTEGER, summary_json TEXT, schema_json TEXT);
CREATE TABLE catalog_entries (
 profile TEXT, key TEXT, kind TEXT, name TEXT, source TEXT, path TEXT, summary TEXT,
 tags_json TEXT, metadata_json TEXT, fields_json TEXT, relations_json TEXT,
 search_text TEXT, built_at_utc TEXT);
CREATE TABLE catalog_scalars (
 profile TEXT, entry_key TEXT, scope TEXT, field_name TEXT, scalar_value TEXT);
""")

    def cursor(self):
        return LocalCursor(self)

    def commit(self):
        self.native.commit()

    def close(self):
        pass  # Public store methods can close a borrowed local fixture safely.


def entry():
    return CatalogEntry(
        key="tool.example", title="Example", kind="tool", import_path="builtins:list",
        summary="Generic helper", minimal_wiring=("value = list()",),
        contract=MappingProxyType({
            "catalog": MappingProxyType({"role": "pool-operation", "concepts": ("投影池",),
                "operations": ("refine",), "boundaries": ("only exact versions",)}),
            "unrelated": MappingProxyType({"preserve": ("all", "source", "fields")}),
        }),
    )


def bundle(source=None):
    source = entry() if source is None else source
    return CatalogBundle(
        components=(sync_module._build_component(source),),
        contexts=(sync_module._build_context_contract(source),),
        usages=(sync_module._build_usage_contract(source),), params=(), methods=(), health=(),
        source_schema=CATALOG_SOURCE_SCHEMA, source_digest=catalog_entries_digest((source,)),
    )


@pytest.fixture(params=["mysql", "postgres"])
def legacy_store(request):
    mysql = request.param == "mysql"
    store = MySQLCatalogStore("mysql://local/local") if mysql else PostgresCatalogStore("postgresql://local/local")
    connection = LocalConnection(mapping_rows=not mysql)
    yield store, connection
    connection.native.close()


def materialize_legacy(store, connection, source_bundle):
    ids = store._upsert_components(connection, source_bundle.components)
    store._upsert_contexts(connection, ids, source_bundle.contexts)
    store._upsert_usages(connection, ids, source_bundle.usages)
    store._replace_field_values(connection, ids, source_bundle.components, source_bundle.contexts, source_bundle.usages)


def test_legacy_sql_roundtrip_preserves_entire_contract_and_guidance_indexes(legacy_store):
    store, connection = legacy_store
    source = bundle()
    materialize_legacy(store, connection, source)
    records = store._catalog_row_records(connection, profile="default")
    restored = store._catalog_entry_from_record(records[0], profile="default")
    assert json.loads(json.dumps(dict(restored.contract), default=list)) == {
        "catalog": {"role": "pool-operation", "concepts": ["投影池"], "operations": ["refine"],
                    "boundaries": ["only exact versions"]},
        "unrelated": {"preserve": ["all", "source", "fields"]},
    }
    assert guidance_payload(restored) == guidance_payload(entry())
    rows = connection.native.execute("SELECT field_name, field_value FROM catalog_field_value").fetchall()
    assert ("concepts", "投影池") in rows and ("role", "pool-operation") in rows
    assert ("operations", "refine") in rows and ("boundaries", "only exact versions") in rows
    assert ("wiring_status", source.usages[0].wiring_status) in rows
    assert any("contract_json" in sql and ("VALUES(contract_json)" in sql or "EXCLUDED.contract_json" in sql)
               for sql, _ in connection.statements)


@pytest.mark.parametrize("field", ["all", "usage"])
def test_legacy_sql_search_and_field_filters_find_guidance(legacy_store, field):
    store, connection = legacy_store
    materialize_legacy(store, connection, bundle())
    for query in ("投影池", "refine", "versions"):
        results = store._catalog_entries_from_query(connection, profile="default", query=query, search_field=field,
            field_filters={"role": ("pool-operation",), "concepts": ("投影池",)})
        assert [item.key for item in results] == ["tool.example"]
    assert store._catalog_entries_from_query(connection, profile="default", field_filters={"role": ("other",)}) == []


def test_database_facets_expose_guidance_and_recomputed_usage_status(legacy_store, monkeypatch):
    from nsgablack.catalog.store import mysql, postgres
    store, connection = legacy_store
    materialize_legacy(store, connection, bundle())
    monkeypatch.setattr(store, "_ensure_schema", lambda connection: None)
    if isinstance(store, MySQLCatalogStore):
        monkeypatch.setattr(mysql, "_connect_mysql", lambda config: connection)
    else:
        monkeypatch.setattr(postgres, "_connect_postgres", lambda config: connection)
        monkeypatch.setattr(store, "_surface_profile_exists", lambda connection, profile: False)
        monkeypatch.setattr(store, "_legacy_query_tables_available", lambda connection: True)
    assert store.field_values("role") == [{"value": "pool-operation", "count": 1}]
    assert store.field_values("concepts") == [{"value": "投影池", "count": 1}]
    assert store.field_values("wiring_status") == [{"value": "signature-checked", "count": 1}]


def test_database_contract_corruption_is_not_silently_replaced_by_an_empty_contract(legacy_store):
    store, _ = legacy_store
    for value in ("[]", "not-json"):
        with pytest.raises(ValueError):
            store._catalog_entry_from_record({"key": "tool.example", "kind": "tool",
                "import_path": "builtins:list", "contract_json": value}, profile="default")


def test_postgres_surface_roundtrip_preserves_contract_status_and_source_digest():
    store = PostgresCatalogStore("postgresql://local/local")
    connection = LocalConnection(mapping_rows=True)
    source = bundle()
    try:
        store._materialize_surface_catalog(connection, source, profile="framework-core")
        entries = store._surface_entries_from_query(connection, profile="framework-core", query="投影池")
        assert len(entries) == 1 and guidance_payload(entries[0]) == guidance_payload(entry())
        assert entries[0].contract["unrelated"]["preserve"] == ["all", "source", "fields"]
        fields_json, = connection.native.execute("SELECT fields_json FROM catalog_entries").fetchone()
        fields = json.loads(fields_json)
        assert fields["wiring_status"] == source.usages[0].wiring_status
        assert fields["wiring_notes"] == list(source.usages[0].wiring_notes)
        schema_json, = connection.native.execute("SELECT schema_json FROM catalog_profiles").fetchone()
        schema = json.loads(schema_json)
        assert schema["source_schema"] == CATALOG_SOURCE_SCHEMA and schema["source_digest"] == source.source_digest
        for query in ("投影池", "refine", "versions"):
            for search_field in ("all", "usage"):
                found = store._surface_entries_from_query(connection, profile="framework-core", query=query,
                    search_field=search_field, field_filters={"role": "pool-operation"})
                assert [item.key for item in found] == ["tool.example"]
    finally:
        connection.native.close()


def test_contract_fingerprint_is_order_independent_and_invalidates_changed_guidance():
    original = entry()
    reordered = replace(original, contract={"unrelated": {"preserve": ["all", "source", "fields"]},
        "catalog": {"boundaries": ["only exact versions"], "operations": ["refine"],
                    "concepts": ["投影池"], "role": "pool-operation"}})
    changed = replace(original, contract={"catalog": {"concepts": ["different"]}})
    assert CATALOG_SOURCE_SCHEMA == "nsgablack.catalog.source.v3"
    assert catalog_entries_digest((original,)) == catalog_entries_digest((reordered,))
    assert catalog_entries_digest((original,)) != catalog_entries_digest((changed,))


class MigrationCursor:
    def __init__(self, connection):
        self.connection = connection

    def execute(self, statement, params=()):
        self.connection.statements.append((" ".join(statement.split()), tuple(params or ())))

    def fetchall(self):
        return [(version,) for version in self.connection.applied]

    def close(self):
        pass


class MigrationConnection:
    def __init__(self, applied):
        self.applied = applied
        self.statements = []

    def cursor(self):
        return MigrationCursor(self)

    def commit(self):
        pass


@pytest.mark.parametrize("backend", ["mysql", "postgres"])
def test_contract_column_migration_nine_runs_once_for_active_legacy_schema(backend):
    store = MySQLCatalogStore("mysql://local/local") if backend == "mysql" else PostgresCatalogStore("postgresql://local/local")
    applied = tuple(range(1, 9)) if backend == "mysql" else (1, 2, 4)
    connection = MigrationConnection(applied)
    store._apply_migrations(connection)
    assert sum("ALTER TABLE catalog_component ADD COLUMN" in sql and "contract_json" in sql
               for sql, _ in connection.statements) == 1
    assert any(params == (9,) for sql, params in connection.statements if "INSERT INTO catalog_schema_migrations" in sql)
    connection = MigrationConnection((*applied, 9))
    store._apply_migrations(connection)
    assert not any("ADD COLUMN" in sql and "contract_json" in sql for sql, _ in connection.statements)


def test_postgres_retired_legacy_tables_are_not_recreated_for_contracts():
    store = PostgresCatalogStore("postgresql://local/local")
    connection = MigrationConnection((1, 2, 3, 4))
    store._apply_migrations(connection)
    assert not any("contract_json" in sql or "CREATE TABLE IF NOT EXISTS catalog_component" in sql
                   for sql, _ in connection.statements)


def test_sync_keeps_typed_usage_status_and_legacy_contract_defaults():
    source = bundle()
    assert source.usages[0].wiring_status == "signature-checked"
    assert "不等于行为已验证" in "; ".join(source.usages[0].wiring_notes)
    component = source.components[0]
    assert component.contract["catalog"]["concepts"] == ("投影池",)
    assert replace(component, contract={}).contract == {}
