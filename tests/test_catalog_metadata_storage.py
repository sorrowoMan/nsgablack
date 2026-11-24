"""ML semantic metadata must survive publication, profiles and cache validation."""
from __future__ import annotations

import json
from dataclasses import replace
from types import MappingProxyType

import pytest

from nsgablack.catalog.facade import _entry_payload
from nsgablack.catalog.fingerprint import catalog_entries_digest
from nsgablack.catalog.registry import CatalogEntry
from nsgablack.catalog.store.mysql import MySQLCatalogStore
from nsgablack.catalog.store.postgres import PostgresCatalogStore
from tests.test_catalog_guidance_storage import (
    LocalConnection,
    MigrationConnection,
    bundle,
    materialize_legacy,
)


def ml_entry():
    return CatalogEntry(
        key="mlblack.model.example", title="ML model", kind="model",
        import_path="builtins:list", minimal_wiring=("model = list()",),
        metadata=MappingProxyType({
            "catalog_framework": "mlblack", "catalog_original_key": "model.example",
            "model_family": "neural", "backends": ("numpy", "torch"),
            "parameter_layout": MappingProxyType({"layers": (8, 4, 1), "dtype": "float32"}),
            # These are source-owned metadata, distinct from DB transport fields.
            "source_scope": "source-owned-scope", "source_hash": "semantic-hash",
        }),
    )


@pytest.mark.parametrize("backend", ("mysql", "postgres-legacy", "postgres-surface"))
@pytest.mark.parametrize("profile", ("default", "framework-core"))
def test_metadata_survives_full_sql_publication_and_public_payload(backend, profile):
    source = ml_entry()
    store = (MySQLCatalogStore("mysql://local/local") if backend == "mysql"
             else PostgresCatalogStore("postgresql://local/local"))
    connection = LocalConnection(mapping_rows=backend != "mysql")
    try:
        if backend == "postgres-surface":
            store._materialize_surface_catalog(connection, bundle(source), profile=profile)
            restored, = store._surface_entries_from_query(connection, profile=profile)
            transport_json, fields_json = connection.native.execute(
                "SELECT metadata_json, fields_json FROM catalog_entries").fetchone()
            assert json.loads(transport_json)["source_scope"] == "framework"
            assert json.loads(fields_json)["metadata"]["source_scope"] == "source-owned-scope"
        else:
            materialize_legacy(store, connection, bundle(source))
            restored, = store._catalog_entries_from_query(connection, profile=profile)
        assert restored.metadata["parameter_layout"] == {"layers": [8, 4, 1], "dtype": "float32"}
        assert restored.metadata["catalog_framework"] == "mlblack"
        assert _entry_payload(restored)["metadata"] == restored.metadata
        assert catalog_entries_digest((restored,)) == catalog_entries_digest((source,))
    finally:
        connection.native.close()


@pytest.mark.parametrize("backend", ("mysql", "postgres"))
def test_old_empty_metadata_is_supported_but_corruption_is_not_silenced(backend):
    store = (MySQLCatalogStore("mysql://local/local") if backend == "mysql"
             else PostgresCatalogStore("postgresql://local/local"))
    record = {"key": "tool.legacy", "kind": "tool", "import_path": "builtins:list"}
    assert store._catalog_entry_from_record(record, profile="default").metadata == {}
    for value in ("[]", "not-json", "42"):
        with pytest.raises(ValueError):
            store._catalog_entry_from_record({**record, "metadata_json": value}, profile="default")


@pytest.mark.parametrize("backend", ("mysql", "postgres-legacy", "postgres-surface"))
def test_large_nested_ml_contract_and_metadata_are_not_truncated(backend):
    source = replace(ml_entry(),
        contract={"model_spec": {"schema": "模型布局" * 12000}},
        metadata={**ml_entry().metadata, "parameter_layout": {"layout": "参数" * 24000}})
    assert len(json.dumps(source.contract, ensure_ascii=False).encode("utf-8")) > 65535
    assert len(json.dumps(source.metadata, ensure_ascii=False).encode("utf-8")) > 65535
    store = (MySQLCatalogStore("mysql://local/local") if backend == "mysql"
             else PostgresCatalogStore("postgresql://local/local"))
    connection = LocalConnection(mapping_rows=backend != "mysql")
    try:
        if backend == "postgres-surface":
            store._materialize_surface_catalog(connection, bundle(source), profile="default")
            restored, = store._surface_entries_from_query(connection, profile="default")
        else:
            materialize_legacy(store, connection, bundle(source))
            restored, = store._catalog_entries_from_query(connection, profile="default")
        assert catalog_entries_digest((restored,)) == catalog_entries_digest((source,))
        assert restored.contract == source.contract
        assert restored.metadata == json.loads(json.dumps(source.metadata, ensure_ascii=False))
    finally:
        connection.native.close()


def test_metadata_changes_invalidate_complete_source_digest():
    source = ml_entry()
    reordered = replace(source, metadata={**dict(reversed(tuple(source.metadata.items()))),
        "parameter_layout": {"dtype": "float32", "layers": [8, 4, 1]}})
    changed = replace(source, metadata={**source.metadata,
        "parameter_layout": {"layers": [8, 4, 2], "dtype": "float32"}})
    assert catalog_entries_digest((source,)) == catalog_entries_digest((reordered,))
    assert catalog_entries_digest((source,)) != catalog_entries_digest((changed,))


@pytest.mark.parametrize("backend", ("mysql", "postgres"))
def test_metadata_column_migrates_existing_rows_once_with_writer_only(backend):
    store = (MySQLCatalogStore("mysql://local/local") if backend == "mysql"
             else PostgresCatalogStore("postgresql://local/local"))
    # PostgreSQL migration 3 means the normalized legacy tables were retired.
    applied = tuple(range(1, 10)) if backend == "mysql" else (1, 2, 4, 5, 6, 7, 8, 9)
    connection = MigrationConnection(applied)
    store._apply_migrations(connection)
    additions = [sql for sql, _ in connection.statements
                 if "ALTER TABLE catalog_component ADD COLUMN" in sql and "metadata_json" in sql]
    assert len(additions) == 1
    assert "LONGTEXT" in additions[0] if backend == "mysql" else "TEXT" in additions[0]
    assert any(params == (10,) for sql, params in connection.statements
               if "INSERT INTO catalog_schema_migrations" in sql)
    repeated = MigrationConnection((*applied, 10))
    store._apply_migrations(repeated)
    assert not any("metadata_json" in sql for sql, _ in repeated.statements)


def test_mysql_contract_capacity_migration_preserves_existing_rows_and_runs_once():
    store = MySQLCatalogStore("mysql://local/local")
    connection = MigrationConnection(tuple(range(1, 11)))
    store._apply_migrations(connection)
    changes = [sql for sql, _ in connection.statements if "ALTER TABLE catalog_component" in sql]
    assert changes == ["ALTER TABLE catalog_component MODIFY COLUMN contract_json LONGTEXT"]
    assert any(params == (11,) for sql, params in connection.statements
               if "INSERT INTO catalog_schema_migrations" in sql)
    assert not any(sql.startswith(("DELETE", "DROP")) for sql, _ in connection.statements)
    repeated = MigrationConnection(tuple(range(1, 12)))
    store._apply_migrations(repeated)
    assert not any("ALTER TABLE catalog_component" in sql for sql, _ in repeated.statements)


def test_mysql_reader_rejects_missing_metadata_column_without_migration():
    connection = LocalConnection()
    connection.native.execute("CREATE TABLE catalog_schema_migrations (version INTEGER)")
    connection.native.execute("ALTER TABLE catalog_component DROP COLUMN metadata_json")
    connection.statements.clear()
    try:
        reader = MySQLCatalogStore("mysql://reader@local/local", readonly=True)
        with pytest.raises(RuntimeError, match="unavailable or outdated at catalog_component"):
            reader._ensure_schema(connection)
        assert all(sql.lstrip().upper().startswith("SELECT") for sql, _ in connection.statements)
        assert "metadata_json" not in {row[1] for row in connection.native.execute("PRAGMA table_info(catalog_component)")}
    finally:
        connection.native.close()


def test_retired_postgres_legacy_tables_are_not_recreated_for_metadata():
    store = PostgresCatalogStore("postgresql://local/local")
    connection = MigrationConnection((1, 2, 3, 4))
    store._apply_migrations(connection)
    assert not any("metadata_json" in sql or "CREATE TABLE IF NOT EXISTS catalog_component" in sql
                   for sql, _ in connection.statements)
