"""Append-only generated Catalog notes, separate from source-owned declarations.

Readers never create tables, import components, or change the source fingerprint.
The existing Catalog database configuration supplies the connection and grants.
"""
from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timezone
import hashlib
import json
import math
import re
import sys
from typing import Any

from .store import resolve_catalog_store
from .store import mysql, postgres


_TABLE = "catalog_knowledge"
_COLUMNS = "record_id, entry_key, source_digest, model, prompt_version, generated_at, record_json"
_FIELDS = ("entry_key", "source_digest", "model", "prompt_version", "generated_at", "note", "evidence", "usage")
_MAX_RECORD_BYTES = 2 * 1024 * 1024


class KnowledgeStoreError(RuntimeError):
    """A safe database error that never includes a connection URL or driver text."""


class KnowledgeUnavailableError(KnowledgeStoreError):
    """The writer has not yet materialized the independent knowledge table."""


class KnowledgeReadOnlyError(KnowledgeStoreError):
    pass


class KnowledgeConflictError(KnowledgeStoreError):
    """An immutable generation identity already has different stored content."""


def _plain_json(value: Any, depth: int = 0) -> Any:
    if depth > 32:
        raise ValueError("Catalog knowledge JSON nesting is too deep")
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("Catalog knowledge JSON numbers must be finite")
        return value
    if isinstance(value, Mapping):
        if any(not isinstance(key, str) for key in value):
            raise ValueError("Catalog knowledge JSON object keys must be strings")
        return {key: _plain_json(item, depth + 1) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain_json(item, depth + 1) for item in value]
    raise ValueError("Catalog knowledge values must be JSON-compatible")


def _text(value: Any, name: str, limit: int) -> str:
    if not isinstance(value, str) or not value.strip() or value != value.strip() or len(value) > limit:
        raise ValueError(f"Catalog knowledge {name} must be a nonempty bounded string")
    return value


def _digest(value: Any) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{64}", value):
        raise ValueError("Catalog knowledge source_digest must be a SHA-256 digest")
    return value


def _normalized_record(record: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(record, Mapping) or set(record) - set(_FIELDS):
        raise ValueError("Catalog knowledge record has unsupported fields")
    required = set(_FIELDS) - {"usage"}
    if not required <= set(record):
        raise ValueError("Catalog knowledge record is incomplete")
    value = _plain_json(record)
    value["entry_key"] = _text(value["entry_key"], "entry_key", 512)
    value["source_digest"] = _digest(value["source_digest"])
    value["model"] = _text(value["model"], "model", 128)
    value["prompt_version"] = _text(value["prompt_version"], "prompt_version", 128)
    stamp = _text(value["generated_at"], "generated_at", 64)
    try:
        parsed = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
    except ValueError:
        raise ValueError("Catalog knowledge generated_at must be an ISO timestamp") from None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("Catalog knowledge generated_at must specify a timezone")
    value["generated_at"] = parsed.astimezone(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")
    if not isinstance(value["note"], dict) or not value["note"]:
        raise ValueError("Catalog knowledge note must be a nonempty object")
    if not isinstance(value["evidence"], list) or any(not isinstance(item, dict) for item in value["evidence"]):
        raise ValueError("Catalog knowledge evidence must be a list of objects")
    value.setdefault("usage", {})
    if not isinstance(value["usage"], dict):
        raise ValueError("Catalog knowledge usage must be an object")
    if len(_encode(value).encode("utf-8")) > _MAX_RECORD_BYTES:
        raise ValueError("Catalog knowledge record exceeds the 2 MiB limit")
    return value


def _encode(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _identity(record: Mapping[str, Any]) -> str:
    return hashlib.sha256(_encode([record[name] for name in ("entry_key", "source_digest", "model", "prompt_version")]).encode()).hexdigest()


def _missing_table(exc: Exception) -> bool:
    # Codes rather than arbitrary driver messages classify production failures.
    if getattr(exc, "sqlstate", None) == "42P01" or getattr(exc, "pgcode", None) == "42P01":
        return True
    args = getattr(exc, "args", ())
    if getattr(exc, "errno", None) == 1146 or (args and args[0] == 1146):
        return True
    # Local SQL adapters use sqlite3, which has no missing-table error code.
    return type(exc).__module__ == "sqlite3" and str(exc).lower() == "no such table: catalog_knowledge"


def _database_error(exc: Exception) -> KnowledgeStoreError:
    if _missing_table(exc):
        return KnowledgeUnavailableError("Catalog knowledge has not been materialized")
    return KnowledgeStoreError("Catalog knowledge database operation failed")


def _cleanup(*resources: Any) -> None:
    primary_error = sys.exc_info()[0] is not None
    failed = False
    for resource in resources:
        if resource is not None:
            try:
                resource.close()
            except Exception:
                failed = True
    if failed and not primary_error:
        raise KnowledgeStoreError("Catalog knowledge database cleanup failed") from None


def _rollback(conn: Any) -> None:
    if conn is not None:
        try:
            conn.rollback()
        except Exception:
            raise KnowledgeStoreError("Catalog knowledge transaction rollback failed") from None


class CatalogKnowledgeStore:
    """Explicit writer initialization and append-only generation records.

    ``put`` reuses identical records and rejects different content at the same
    entry/digest/model/prompt identity. New source or generation versions append
    a record; old notes remain available for exact-digest inspection.
    """

    def __init__(self, catalog_store: Any, *, readonly: bool = True):
        self.backend = str(getattr(catalog_store, "backend", ""))
        if self.backend not in {"mysql", "postgresql"}:
            raise ValueError("Catalog knowledge requires a MySQL or PostgreSQL Catalog store")
        self._cfg = catalog_store._cfg
        self.readonly = bool(readonly or getattr(catalog_store, "readonly", False))

    def _connect(self):
        try:
            connector = mysql._connect_mysql if self.backend == "mysql" else postgres._connect_postgres
            return connector(self._cfg)
        except Exception as exc:
            raise _database_error(exc) from None

    def _writable(self):
        if self.readonly:
            raise KnowledgeReadOnlyError("Catalog knowledge store is read-only")

    def ensure_schema(self) -> None:
        self._writable()
        conn, cursor = None, None
        try:
            conn = self._connect()
            cursor = conn.cursor()
            if self.backend == "mysql":
                cursor.execute("""CREATE TABLE IF NOT EXISTS catalog_knowledge (
 record_id VARCHAR(64) PRIMARY KEY,
 entry_key VARCHAR(512) NOT NULL,
 source_digest VARCHAR(64) NOT NULL,
 model VARCHAR(128) NOT NULL,
 prompt_version VARCHAR(128) NOT NULL,
 generated_at VARCHAR(32) NOT NULL,
 record_json LONGTEXT NOT NULL,
 INDEX catalog_knowledge_entry_time (entry_key, generated_at, record_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin""")
            else:
                cursor.execute("""CREATE TABLE IF NOT EXISTS catalog_knowledge (
 record_id VARCHAR(64) PRIMARY KEY,
 entry_key VARCHAR(512) NOT NULL,
 source_digest VARCHAR(64) NOT NULL,
 model VARCHAR(128) NOT NULL,
 prompt_version VARCHAR(128) NOT NULL,
 generated_at VARCHAR(32) NOT NULL,
 record_json TEXT NOT NULL
)""")
                cursor.execute("CREATE INDEX IF NOT EXISTS catalog_knowledge_entry_time ON catalog_knowledge (entry_key, generated_at, record_id)")
            conn.commit()
        except KnowledgeStoreError:
            raise
        except Exception as exc:
            raise _database_error(exc) from None
        finally:
            _cleanup(cursor, conn)

    def status(self) -> dict[str, Any]:
        """Probe availability using SELECT only; connection/permission errors propagate."""
        conn, cursor = None, None
        try:
            conn = self._connect()
            cursor = conn.cursor()
            cursor.execute(f"SELECT {_COLUMNS} FROM {_TABLE} WHERE 1=0")
            return {"available": True, "backend": self.backend}
        except KnowledgeStoreError:
            raise
        except Exception as exc:
            if _missing_table(exc):
                return {"available": False, "reason": "not_materialized", "backend": self.backend}
            raise _database_error(exc) from None
        finally:
            _cleanup(cursor, conn)

    @staticmethod
    def _record(row: Any) -> dict[str, Any]:
        if isinstance(row, Mapping):
            fields = dict(row)
        else:
            fields = dict(zip(_COLUMNS.split(", "), row))
        try:
            raw = fields["record_json"]
            decoded = json.loads(raw) if isinstance(raw, (str, bytes)) else raw
            record = _normalized_record(decoded)
            if fields["record_id"] != _identity(record) or any(fields[name] != record[name] for name in
                    ("entry_key", "source_digest", "model", "prompt_version", "generated_at")):
                raise ValueError("record identity mismatch")
            return record
        except (ValueError, TypeError, KeyError):
            raise KnowledgeStoreError("Catalog knowledge contains an invalid stored record") from None

    def get(self, entry_key: str, source_digest: str | None = None, *, model: str | None = None,
            prompt_version: str | None = None) -> dict[str, Any] | None:
        filters, params = ["entry_key=%s"], [_text(entry_key, "entry_key", 512)]
        for name, value in (("source_digest", source_digest), ("model", model), ("prompt_version", prompt_version)):
            if value is not None:
                filters.append(name + "=%s")
                params.append(_digest(value) if name == "source_digest" else _text(value, name, 128))
        conn, cursor = None, None
        try:
            conn = self._connect()
            cursor = conn.cursor()
            cursor.execute(f"SELECT {_COLUMNS} FROM {_TABLE} WHERE " + " AND ".join(filters)
                           + " ORDER BY generated_at DESC, record_id DESC LIMIT 1", tuple(params))
            row = cursor.fetchone()
            return None if row is None else self._record(row)
        except KnowledgeStoreError:
            raise
        except Exception as exc:
            raise _database_error(exc) from None
        finally:
            _cleanup(cursor, conn)

    def list_latest(self) -> list[dict[str, Any]]:
        conn, cursor = None, None
        try:
            conn = self._connect()
            cursor = conn.cursor()
            columns = ", ".join("k." + name for name in _COLUMNS.split(", "))
            cursor.execute(f"""SELECT {columns} FROM {_TABLE} k
WHERE NOT EXISTS (SELECT 1 FROM {_TABLE} newer WHERE newer.entry_key=k.entry_key
 AND (newer.generated_at>k.generated_at OR
      (newer.generated_at=k.generated_at AND newer.record_id>k.record_id)))
ORDER BY k.entry_key""")
            return [self._record(row) for row in cursor.fetchall()]
        except KnowledgeStoreError:
            raise
        except Exception as exc:
            raise _database_error(exc) from None
        finally:
            _cleanup(cursor, conn)

    def put(self, record: Mapping[str, Any]) -> dict[str, Any]:
        self._writable()
        value = _normalized_record(record)
        identity = _identity(value)
        encoded = _encode(value)
        conn, cursor = None, None
        try:
            conn = self._connect()
            cursor = conn.cursor()
            tail = (" ON DUPLICATE KEY UPDATE record_id=record_id" if self.backend == "mysql"
                    else " ON CONFLICT (record_id) DO NOTHING")
            cursor.execute(f"INSERT INTO {_TABLE} ({_COLUMNS}) VALUES (%s,%s,%s,%s,%s,%s,%s)" + tail,
                           (identity, value["entry_key"], value["source_digest"], value["model"],
                            value["prompt_version"], value["generated_at"], encoded))
            cursor.execute(f"SELECT {_COLUMNS} FROM {_TABLE} WHERE record_id=%s", (identity,))
            stored = self._record(cursor.fetchone())
            if stored != value:
                raise KnowledgeConflictError("Catalog knowledge identity already contains different immutable content")
            conn.commit()
            return stored
        except KnowledgeStoreError:
            _rollback(conn)
            raise
        except Exception as exc:
            _rollback(conn)
            raise _database_error(exc) from None
        finally:
            _cleanup(cursor, conn)


def resolve_knowledge_store(*, readonly: bool = True, db_url: str | None = None) -> CatalogKnowledgeStore:
    """Resolve the existing Catalog connection without materializing any table."""
    try:
        store = resolve_catalog_store(url=db_url, readonly=readonly)
    except Exception:
        raise KnowledgeStoreError("Catalog knowledge database configuration is unavailable") from None
    return CatalogKnowledgeStore(store, readonly=readonly)


__all__ = ["CatalogKnowledgeStore", "KnowledgeStoreError", "KnowledgeUnavailableError",
           "KnowledgeReadOnlyError", "KnowledgeConflictError", "resolve_knowledge_store"]
