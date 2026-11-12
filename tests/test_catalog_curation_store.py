"""Generated knowledge persistence never mutates factual Catalog definitions."""
from __future__ import annotations

from copy import deepcopy
import json
import re
import sqlite3

import pytest

from nsgablack.catalog import curation_store as module
from nsgablack.catalog.store.mysql import MySQLCatalogStore
from nsgablack.catalog.store.postgres import PostgresCatalogStore


class LocalCursor:
    def __init__(self, conn):
        self.conn = conn
        self.native = conn.native.cursor()

    def execute(self, sql, params=()):
        self.conn.statements.append((sql, tuple(params)))
        if "CREATE TABLE" in sql:
            sql = re.sub(r",\s*INDEX catalog_knowledge_entry_time \([^\n]+\)", "", sql)
            sql = sql.split("ENGINE=", 1)[0]
        sql = sql.replace(" ON DUPLICATE KEY UPDATE record_id=record_id", " ON CONFLICT (record_id) DO NOTHING")
        return self.native.execute(sql.replace("%s", "?"), params)

    def _row(self, row):
        if row is None or not self.conn.mapping:
            return row
        return dict(zip((column[0] for column in self.native.description), row))

    def fetchone(self):
        return self._row(self.native.fetchone())

    def fetchall(self):
        return [self._row(row) for row in self.native.fetchall()]

    def close(self):
        self.native.close()


class LocalConnection:
    def __init__(self, *, mapping=False):
        self.native = sqlite3.connect(":memory:")
        self.mapping = mapping
        self.statements = []
        self.commits = self.rollbacks = 0

    def cursor(self):
        return LocalCursor(self)

    def commit(self):
        self.commits += 1
        self.native.commit()

    def rollback(self):
        self.rollbacks += 1
        self.native.rollback()

    def close(self):
        pass  # A test borrows the connection across independent public calls.


@pytest.fixture(params=("mysql", "postgresql"))
def storage(request, monkeypatch):
    mysql = request.param == "mysql"
    factual = MySQLCatalogStore("mysql://local/catalog") if mysql else PostgresCatalogStore("postgresql://local/catalog")
    conn = LocalConnection(mapping=not mysql)
    driver = module.mysql if mysql else module.postgres
    monkeypatch.setattr(driver, "_connect_mysql" if mysql else "_connect_postgres", lambda cfg: conn)
    writer = module.CatalogKnowledgeStore(factual, readonly=False)
    reader = module.CatalogKnowledgeStore(factual, readonly=True)
    yield writer, reader, conn
    conn.native.close()


def record(**changes):
    value = {
        "entry_key": "mlblack.codec.linear_point", "source_digest": "a" * 64,
        "model": "deepseek-example", "prompt_version": "catalog-notes/v1",
        "generated_at": "2026-10-22T14:00:00+08:00",
        "note": {"summary": "模型参数与搜索Unit分别维护", "evidence_ids": ["source-1"]},
        "evidence": [{"id": "source-1", "path": "mlblack/codecs/linear.py", "start_line": 10,
                      "end_line": 12, "sha256": "b" * 64, "text": "class LinearPointCodec: ..."}],
        "usage": {"prompt_tokens": 100, "completion_tokens": 50},
    }
    return {**value, **changes}


def test_explicit_writer_schema_and_read_only_absence_are_separate(storage):
    writer, reader, conn = storage
    assert reader.status() == {"available": False, "reason": "not_materialized", "backend": reader.backend}
    with pytest.raises(module.KnowledgeUnavailableError):
        reader.list_latest()
    with pytest.raises(module.KnowledgeUnavailableError):
        reader.get("tool.missing")
    assert all(sql.startswith("SELECT") for sql, _ in conn.statements)
    writer.ensure_schema()
    writer.ensure_schema()  # Explicit initialization is idempotent.
    assert reader.status() == {"available": True, "backend": reader.backend}
    assert reader.list_latest() == []
    assert reader.get("tool.missing") is None
    tables = {row[0] for row in conn.native.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert tables == {"catalog_knowledge"}
    if writer.backend == "mysql":
        ddl = next(sql for sql, _ in conn.statements if sql.startswith("CREATE TABLE"))
        assert "LONGTEXT" in ddl and "COLLATE=utf8mb4_bin" in ddl


def test_record_roundtrip_and_retry_preserve_complete_evidence(storage):
    writer, reader, conn = storage
    writer.ensure_schema()
    original = record()
    saved = writer.put(original)
    assert saved["generated_at"] == "2026-10-22T06:00:00.000000Z"
    assert saved["evidence"] == original["evidence"]
    assert saved["usage"] == original["usage"]
    assert original["generated_at"].endswith("+08:00")
    assert writer.put(deepcopy(original)) == saved
    assert reader.get(original["entry_key"], original["source_digest"], model=original["model"],
                      prompt_version=original["prompt_version"]) == saved
    assert reader.get(original["entry_key"], original["source_digest"], model="different") is None
    assert reader.list_latest() == [saved]
    assert conn.native.execute("SELECT COUNT(*) FROM catalog_knowledge").fetchone()[0] == 1
    # Returned data is detached from storage and its caller's mutable values.
    saved["note"]["summary"] = "changed outside store"
    assert reader.get(original["entry_key"])["note"] == original["note"]


def test_identity_is_immutable_and_versions_remain_exactly_addressable(storage):
    writer, reader, conn = storage
    writer.ensure_schema()
    first = writer.put(record())
    with pytest.raises(module.KnowledgeConflictError):
        writer.put(record(note={"summary": "unrelated replacement"}))
    assert conn.rollbacks == 1
    assert reader.get(first["entry_key"]) == first
    newer = writer.put(record(source_digest="c" * 64, generated_at="2026-10-22T09:00:00Z"))
    assert reader.list_latest() == [newer]
    assert reader.get(first["entry_key"], first["source_digest"]) == first
    model_version = writer.put(record(model="another-model", generated_at="2026-10-22T10:00:00Z"))
    assert reader.get(first["entry_key"], first["source_digest"], model=first["model"],
                      prompt_version=first["prompt_version"]) == first
    assert reader.get(first["entry_key"], first["source_digest"], model="another-model") == model_version
    assert conn.native.execute("SELECT COUNT(*) FROM catalog_knowledge").fetchone()[0] == 3


def test_reader_never_connects_for_a_write(storage):
    _writer, reader, conn = storage
    for action in (reader.ensure_schema, lambda: reader.put(record())):
        with pytest.raises(module.KnowledgeReadOnlyError):
            action()
    assert conn.statements == [] and conn.commits == 0


def test_invalid_records_do_not_start_database_operations(storage):
    writer, _reader, conn = storage
    bad = [record(source_digest="not-a-digest"), record(generated_at="2026-10-22T00:00:00"),
           record(note={}), record(evidence="source"), record(usage={"count": float("nan")}),
           record(note={"item": object()}), {**record(), "api_key": "unwanted credential field"}]
    for item in bad:
        with pytest.raises(ValueError):
            writer.put(item)
    assert conn.statements == []


def test_large_knowledge_and_literal_entry_keys_survive(storage):
    writer, reader, _conn = storage
    writer.ensure_schema()
    original = record(entry_key="tool.' OR 1=1 --", note={"summary": "来源" * 40000})
    saved = writer.put(original)
    assert len(json.dumps(saved["note"], ensure_ascii=False).encode()) > 65535
    assert reader.get(original["entry_key"]) == saved
    assert reader.get("tool.unrelated") is None


def test_corrupt_record_does_not_become_a_valid_note(storage):
    writer, reader, conn = storage
    writer.ensure_schema()
    writer.put(record())
    conn.native.execute("UPDATE catalog_knowledge SET record_json='{}'")
    with pytest.raises(module.KnowledgeStoreError, match="invalid stored record"):
        reader.list_latest()


def test_database_failures_are_safe_and_not_reported_as_missing(monkeypatch):
    raw_error = RuntimeError("driver error containing password=private-value and private URL")
    monkeypatch.setattr(module.mysql, "_connect_mysql", lambda cfg: (_ for _ in ()).throw(raw_error))
    store = module.CatalogKnowledgeStore(MySQLCatalogStore("mysql://local/catalog"))
    with pytest.raises(module.KnowledgeStoreError) as error:
        store.status()
    assert "private-value" not in str(error.value)
    assert "URL" not in str(error.value)
    assert not isinstance(error.value, module.KnowledgeUnavailableError)


def test_resolver_uses_existing_grants_without_opening_database(monkeypatch):
    calls = []
    factual = MySQLCatalogStore("mysql://local/catalog", readonly=True)
    monkeypatch.setattr(module, "resolve_catalog_store", lambda **kwargs: calls.append(kwargs) or factual)
    monkeypatch.setattr(module.mysql, "_connect_mysql", lambda cfg: pytest.fail("resolver connected"))
    store = module.resolve_knowledge_store(readonly=True, db_url="mysql://local/catalog")
    assert store.readonly
    assert calls == [{"url": "mysql://local/catalog", "readonly": True}]
    # A factual read grant cannot be widened by wrapping it as a writer.
    with pytest.raises(module.KnowledgeReadOnlyError):
        module.CatalogKnowledgeStore(factual, readonly=False).ensure_schema()
