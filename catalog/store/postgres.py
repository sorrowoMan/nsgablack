from __future__ import annotations

import json
import os
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, List, Mapping, Optional, Sequence, Tuple
from urllib.parse import urlparse

try:
    from psycopg import connect as _pg_connect
    from psycopg.rows import dict_row as _pg_dict_row
except Exception:  # pragma: no cover
    _pg_connect = None
    _pg_dict_row = None

from ..contracts import (
    CatalogBundle,
    CatalogComponentContract,
    ContextContract,
    HealthContract,
    MethodContract,
    ParamContract,
    UsageContract,
)
from ..contract_relations import build_contract_neighbor_sections, enrich_entry_relation_fields
from ..registry import CatalogEntry, _expand_token_groups
from .mysql import (
    _CONTEXT_FIELD_NAMES,
    _SEARCHABLE_FIELD_NAMES,
    _USAGE_FIELD_NAMES,
    _apply_profile_to_entry,
    _like_pattern,
    _normalize_field_filters,
    _normalize_strings,
    _profile_sql_filters,
    _read_mysql_config_file,
    _sort_catalog_entries,
    _trim_field_value,
    _truthy_env,
)

_SURFACE_FIELD_ORDER = (
    "key",
    "title",
    "kind",
    "import_path",
    "module",
    "symbol",
    "tags",
    "summary",
    "companions",
    "context_requires",
    "context_provides",
    "context_mutates",
    "context_cache",
    "context_notes",
    "artifact_requires",
    "artifact_provides",
    "phase_in",
    "phase_out",
    "use_when",
    "minimal_wiring",
    "required_companions",
    "config_keys",
    "example_entry",
)

_SURFACE_FIELD_GROUPS = {
    "base": ("key", "title", "kind", "import_path", "module", "symbol", "tags", "summary", "companions"),
    "contracts": (
        "context_requires",
        "context_provides",
        "context_mutates",
        "context_cache",
        "context_notes",
        "artifact_requires",
        "artifact_provides",
        "phase_in",
        "phase_out",
    ),
    "usage": ("use_when", "minimal_wiring", "required_companions", "config_keys", "example_entry"),
}

_FORMAL_SURFACE_TABLES = (
    "catalog_profiles",
    "catalog_entries",
    "catalog_scalars",
)

_LEGACY_DECOMPOSED_TABLES = (
    "catalog_component",
    "catalog_context_contract",
    "catalog_usage_contract",
    "catalog_param_contract",
    "catalog_method_contract",
    "catalog_health",
    "catalog_field_value",
)

_LEGACY_QUERY_TABLES = (
    "catalog_component",
    "catalog_context_contract",
    "catalog_usage_contract",
    "catalog_field_value",
)

_LEGACY_RETIRE_MIGRATION_VERSION = 3


def _env_url_uses_postgres(url: str) -> bool:
    raw = str(url or "").strip()
    if not raw:
        return False
    try:
        scheme = str(urlparse(raw).scheme or "").strip().lower()
    except Exception:
        return False
    return scheme in {"postgres", "postgresql", "postgresql+psycopg", "postgresql+psycopg2"}


def _postgres_block() -> Dict[str, object]:
    cfg_data = _read_mysql_config_file()
    if not isinstance(cfg_data, dict):
        return {}
    for key in ("postgres", "postgresql"):
        block = cfg_data.get(key)
        if isinstance(block, dict):
            return block
    return {}


@dataclass(frozen=True)
class PostgresCatalogConfig:
    host: str
    port: int
    user: str
    password: str
    database: str
    connect_timeout: int = 10


def parse_postgres_url(url: str) -> PostgresCatalogConfig:
    parsed = urlparse(url)
    if str(parsed.scheme or "").strip().lower() not in {"postgres", "postgresql", "postgresql+psycopg", "postgresql+psycopg2"}:
        raise ValueError(f"Unsupported PostgreSQL URL scheme: {parsed.scheme}")
    return PostgresCatalogConfig(
        host=parsed.hostname or "127.0.0.1",
        port=int(parsed.port or 5432),
        user=parsed.username or "postgres",
        password=parsed.password or "",
        database=(parsed.path or "").lstrip("/") or "postgres",
    )


def _resolve_postgres_config() -> tuple[Optional[str], Optional[PostgresCatalogConfig], bool]:
    env_url = os.environ.get("NSGABLACK_CATALOG_DB_URL", "").strip()
    if _env_url_uses_postgres(env_url):
        return env_url, parse_postgres_url(env_url), _truthy_env("NSGABLACK_CATALOG_DB_READONLY")

    pg_block = _postgres_block()
    enabled = bool(pg_block.get("enabled", False))
    if not enabled:
        return None, None, False

    url = str(pg_block.get("url", "") or "").strip()
    if url:
        readonly = bool(pg_block.get("readonly", False))
        return url, parse_postgres_url(url), readonly

    cfg = PostgresCatalogConfig(
        host=str(pg_block.get("host", "127.0.0.1")),
        port=int(pg_block.get("port", 5432)),
        user=str(pg_block.get("user", "postgres")),
        password=str(pg_block.get("password", "")),
        database=str(pg_block.get("database", "postgres")),
        connect_timeout=int(pg_block.get("connect_timeout", 10)),
    )
    readonly = bool(pg_block.get("readonly", False))
    return None, cfg, readonly


def postgres_config_enabled() -> bool:
    env_url = os.environ.get("NSGABLACK_CATALOG_DB_URL", "").strip()
    if _env_url_uses_postgres(env_url):
        return True
    return bool(_postgres_block().get("enabled", False))


def postgres_config_mode() -> str:
    env_mode = os.environ.get("NSGABLACK_CATALOG_DB_MODE", "").strip().lower()
    if env_mode in {"only", "prefer", "off", "disabled"}:
        return "off" if env_mode == "disabled" else env_mode
    mode = str(_postgres_block().get("mode", "") or "").strip().lower()
    if mode in {"only", "prefer", "off", "disabled"}:
        return "off" if mode == "disabled" else mode
    return "prefer"


def postgres_config_info() -> Dict[str, object]:
    env_url = os.environ.get("NSGABLACK_CATALOG_DB_URL", "").strip()
    env_cfg = os.environ.get("NSGABLACK_CATALOG_DB_CONFIG", "").strip()
    block = _postgres_block()
    return {
        "enabled": postgres_config_enabled(),
        "mode": postgres_config_mode(),
        "backend": "postgresql",
        "config_env": env_cfg or None,
        "explicit_url_env": _env_url_uses_postgres(env_url),
        "readonly": bool(block.get("readonly", False)) or _truthy_env("NSGABLACK_CATALOG_DB_READONLY"),
    }


def _connect_postgres(cfg: PostgresCatalogConfig):
    if _pg_connect is None:
        raise RuntimeError("PostgreSQL driver missing: install psycopg.")
    conn = _pg_connect(
        host=cfg.host,
        port=int(cfg.port),
        user=cfg.user,
        password=cfg.password,
        dbname=cfg.database,
        connect_timeout=int(cfg.connect_timeout),
        row_factory=_pg_dict_row,
    )
    return conn


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _json_dumps(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, default=str)


def _json_loads(text: object) -> object:
    raw = str(text or "").strip()
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except Exception:
        return {}


def _pg_table_exists(cur, table_name: str) -> bool:
    cur.execute("SELECT to_regclass(%s) AS table_ref", (str(table_name),))
    row = cur.fetchone()
    if not row:
        return False
    value = row.get("table_ref") if isinstance(row, Mapping) else row[0]
    return bool(value)


def _pg_table_row_count(cur, table_name: str) -> int:
    cur.execute(f'SELECT COUNT(*) AS count FROM "{table_name}"')
    row = cur.fetchone()
    if not row:
        return 0
    return int((row.get("count") if isinstance(row, Mapping) else row[0]) or 0)


def _entry_values(entry: CatalogEntry, field_name: str) -> Tuple[str, ...]:
    key = str(field_name or "").strip()
    if key == "key":
        return (entry.key,) if entry.key else ()
    if key == "title":
        return (entry.title,) if entry.title else ()
    if key == "kind":
        return (entry.kind,) if entry.kind else ()
    if key == "import_path":
        return (entry.import_path,) if entry.import_path else ()
    if key == "module":
        value = entry.import_path.partition(":")[0].strip()
        return (value,) if value else ()
    if key == "symbol":
        value = entry.import_path.partition(":")[2].strip()
        return (value,) if value else ()
    if key == "summary":
        return (entry.summary,) if entry.summary else ()
    value = getattr(entry, key, ())
    if isinstance(value, str):
        text = value.strip()
        return (text,) if text else ()
    return tuple(str(item).strip() for item in (value or ()) if str(item).strip())


def _entry_to_surface_fields(entry: CatalogEntry, *, source_scope: str = "", source_hash: str = "") -> dict[str, object]:
    return {
        "key": entry.key,
        "title": entry.title,
        "kind": entry.kind,
        "import_path": entry.import_path,
        "module": entry.import_path.partition(":")[0].strip(),
        "symbol": entry.import_path.partition(":")[2].strip(),
        "tags": list(entry.tags),
        "summary": entry.summary,
        "companions": list(entry.companions),
        "context_requires": list(entry.context_requires),
        "context_provides": list(entry.context_provides),
        "context_mutates": list(entry.context_mutates),
        "context_cache": list(entry.context_cache),
        "context_notes": list(entry.context_notes),
        "artifact_requires": list(getattr(entry, "artifact_requires", ()) or ()),
        "artifact_provides": list(getattr(entry, "artifact_provides", ()) or ()),
        "phase_in": list(getattr(entry, "phase_in", ()) or ()),
        "phase_out": list(getattr(entry, "phase_out", ()) or ()),
        "use_when": list(entry.use_when),
        "minimal_wiring": list(entry.minimal_wiring),
        "required_companions": list(entry.required_companions),
        "config_keys": list(entry.config_keys),
        "example_entry": entry.example_entry,
        "detail_ref": entry.detail_ref,
        "source_scope": source_scope,
        "source_hash": source_hash,
    }


def _entry_to_relations(entry: CatalogEntry) -> dict[str, object]:
    return {
        "companions": list(entry.companions),
        "required_companions": list(entry.required_companions),
        "artifact_provides": list(getattr(entry, "artifact_provides", ()) or ()),
        "artifact_requires": list(getattr(entry, "artifact_requires", ()) or ()),
        "phase_out": list(getattr(entry, "phase_out", ()) or ()),
        "phase_in": list(getattr(entry, "phase_in", ()) or ()),
    }


def _entry_scalar_rows(entry: CatalogEntry) -> List[dict[str, str]]:
    rows: List[dict[str, str]] = []

    def add(scope: str, field_name: str, values: object) -> None:
        seen: set[str] = set()
        for raw in _normalize_strings(values):
            value = str(raw).strip()
            if not value:
                continue
            token = f"{scope}|{field_name}|{value.lower()}"
            if token in seen:
                continue
            seen.add(token)
            rows.append({"scope": scope, "field_name": field_name, "scalar_value": value})

    add("base", "key", entry.key)
    add("base", "title", entry.title)
    add("base", "name", entry.title)
    add("base", "kind", entry.kind)
    add("base", "import_path", entry.import_path)
    add("base", "module", entry.import_path.partition(":")[0].strip())
    add("base", "symbol", entry.import_path.partition(":")[2].strip())
    add("base", "summary", entry.summary)
    add("base", "tags", entry.tags)
    add("base", "companions", entry.companions)
    add("context", "context_requires", entry.context_requires)
    add("context", "context_provides", entry.context_provides)
    add("context", "context_mutates", entry.context_mutates)
    add("context", "context_cache", entry.context_cache)
    add("context", "context_notes", entry.context_notes)
    add("context", "artifact_requires", getattr(entry, "artifact_requires", ()))
    add("context", "artifact_provides", getattr(entry, "artifact_provides", ()))
    add("context", "phase_in", getattr(entry, "phase_in", ()))
    add("context", "phase_out", getattr(entry, "phase_out", ()))
    add("usage", "use_when", entry.use_when)
    add("usage", "minimal_wiring", entry.minimal_wiring)
    add("usage", "required_companions", entry.required_companions)
    add("usage", "config_keys", entry.config_keys)
    add("usage", "example_entry", entry.example_entry)
    return rows


def _entry_search_text(entry: CatalogEntry) -> str:
    tokens: List[str] = []
    for field_name in _SURFACE_FIELD_ORDER:
        tokens.extend(value.lower() for value in _entry_values(entry, field_name))
    return " ".join(token for token in tokens if token)


def _surface_summary(entries: Sequence[CatalogEntry], *, profile: str) -> dict[str, object]:
    by_kind = Counter(entry.kind for entry in entries)
    tags = sorted({tag for entry in entries for tag in entry.tags})
    return {
        "profile": str(profile),
        "scope": "framework",
        "project_root": None,
        "project_found": True,
        "include_global": False,
        "total": len(entries),
        "by_kind": dict(sorted(by_kind.items())),
        "unique_tags": len(tags),
    }


def _surface_schema(entries: Sequence[CatalogEntry], *, profile: str) -> dict[str, object]:
    fields = tuple(field_name for field_name in _SURFACE_FIELD_ORDER if any(_entry_values(entry, field_name) for entry in entries))
    kinds = tuple(sorted({entry.kind for entry in entries}))
    return {
        "profile": str(profile),
        "scope": "framework",
        "project_root": None,
        "project_found": True,
        "include_global": False,
        "kind": None,
        "kinds": kinds,
        "fields": fields,
        "field_groups": _SURFACE_FIELD_GROUPS,
        "search_fields": ("all", "name", "tag", "context", "usage"),
        "counts": {"entries": len(entries)},
    }


class PostgresCatalogStore:
    backend = "postgresql"

    def __init__(self, url: Optional[str] = None, *, readonly: Optional[bool] = None) -> None:
        cfg: Optional[PostgresCatalogConfig] = None
        resolved_url: Optional[str] = None
        resolved_readonly = False
        if url:
            resolved_url = url
            cfg = parse_postgres_url(url)
        else:
            resolved_url, cfg, resolved_readonly = _resolve_postgres_config()
        if cfg is None and resolved_url:
            cfg = parse_postgres_url(resolved_url)
        if cfg is None:
            raise RuntimeError(
                "PostgreSQL catalog config missing. Set NSGABLACK_CATALOG_DB_URL or enable catalog/db.toml [postgres]."
            )
        self._url = resolved_url or ""
        self._cfg = cfg
        self._readonly = bool(resolved_readonly if readonly is None else readonly)

    @property
    def readonly(self) -> bool:
        return self._readonly

    def _ensure_migration_table(self, conn) -> None:
        cur = conn.cursor()
        cur.execute(
            """
CREATE TABLE IF NOT EXISTS catalog_schema_migrations (
  version INTEGER PRIMARY KEY,
  applied_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
)
"""
        )
        conn.commit()
        cur.close()

    def _legacy_support_retired(self, conn) -> bool:
        cur = conn.cursor()
        try:
            if not _pg_table_exists(cur, "catalog_schema_migrations"):
                return False
            cur.execute(
                "SELECT 1 FROM catalog_schema_migrations WHERE version = %s LIMIT 1",
                (int(_LEGACY_RETIRE_MIGRATION_VERSION),),
            )
            return bool(cur.fetchone())
        finally:
            cur.close()

    def _legacy_query_tables_available(self, conn) -> bool:
        cur = conn.cursor()
        try:
            return all(_pg_table_exists(cur, table_name) for table_name in _LEGACY_QUERY_TABLES)
        finally:
            cur.close()

    def has_profile(self, *, profile: str = "default") -> bool:
        conn = _connect_postgres(self._cfg)
        try:
            self._ensure_schema(conn)
            if self._surface_profile_exists(conn, profile=str(profile)):
                return True
            return self._legacy_query_tables_available(conn)
        finally:
            conn.close()

    def _ensure_schema(self, conn) -> None:
        self._apply_migrations(conn)
        self._ensure_surface_tables(conn)
        if not self._legacy_support_retired(conn):
            self._ensure_field_value_table(conn)
            self._ensure_field_value_index(conn)

    def _ensure_surface_tables(self, conn) -> None:
        cur = conn.cursor()
        cur.execute(
            """
CREATE TABLE IF NOT EXISTS catalog_profiles (
  profile VARCHAR(255) PRIMARY KEY,
  built_at_utc VARCHAR(64) NOT NULL,
  total INTEGER NOT NULL,
  summary_json TEXT NOT NULL,
  schema_json TEXT NOT NULL
)
"""
        )
        cur.execute(
            """
CREATE TABLE IF NOT EXISTS catalog_entries (
  profile VARCHAR(255) NOT NULL,
  key VARCHAR(255) NOT NULL,
  kind VARCHAR(64) NOT NULL,
  name VARCHAR(255) NOT NULL,
  source VARCHAR(255) NOT NULL,
  path TEXT NULL,
  summary TEXT NOT NULL,
  tags_json TEXT NOT NULL,
  metadata_json TEXT NOT NULL,
  fields_json TEXT NOT NULL,
  relations_json TEXT NOT NULL,
  search_text TEXT NOT NULL,
  built_at_utc VARCHAR(64) NOT NULL,
  PRIMARY KEY (profile, key)
)
"""
        )
        cur.execute("CREATE INDEX IF NOT EXISTS idx_catalog_entries_kind ON catalog_entries (kind)")
        cur.execute(
            """
CREATE TABLE IF NOT EXISTS catalog_scalars (
  profile VARCHAR(255) NOT NULL,
  entry_key VARCHAR(255) NOT NULL,
  scope VARCHAR(32) NOT NULL,
  field_name VARCHAR(255) NOT NULL,
  scalar_value TEXT NOT NULL
)
"""
        )
        cur.execute("CREATE INDEX IF NOT EXISTS idx_catalog_scalars_profile ON catalog_scalars (profile)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_catalog_scalars_entry_key ON catalog_scalars (entry_key)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_catalog_scalars_field_name ON catalog_scalars (field_name)")
        conn.commit()
        cur.close()

    def _ensure_field_value_table(self, conn) -> None:
        cur = conn.cursor()
        cur.execute(
            """
CREATE TABLE IF NOT EXISTS catalog_field_value (
  id SERIAL PRIMARY KEY,
  component_id INTEGER NOT NULL,
  field_scope TEXT NOT NULL,
  field_name TEXT NOT NULL,
  field_value TEXT NOT NULL,
  field_value_norm TEXT NOT NULL
)
"""
        )
        cur.execute("CREATE INDEX IF NOT EXISTS idx_catalog_field_component ON catalog_field_value (component_id)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_catalog_field_name ON catalog_field_value (field_name)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_catalog_field_name_norm ON catalog_field_value (field_name, field_value_norm)")
        conn.commit()
        cur.close()

    def _apply_migrations(self, conn) -> None:
        self._ensure_migration_table(conn)
        cur = conn.cursor()
        cur.execute("SELECT version FROM catalog_schema_migrations")
        rows = cur.fetchall() or []
        applied = {int(row["version"] if isinstance(row, Mapping) else row[0]) for row in rows}
        legacy_retired = int(_LEGACY_RETIRE_MIGRATION_VERSION) in applied

        def safe_exec(stmt: str) -> None:
            try:
                cur.execute(stmt)
            except Exception as exc:
                msg = str(exc).lower()
                if "already exists" in msg or "duplicate" in msg or "已经存在" in msg:
                    cur.execute("ROLLBACK TO SAVEPOINT safe_mig;")
                    cur.execute("SAVEPOINT safe_mig;")
                    return
                raise

        cur.execute("SAVEPOINT safe_mig;")

        migrations: List[tuple[int, Sequence[str]]] = []
        if not legacy_retired:
            migrations.extend(
                [
                    (
                        1,
                        (
                            """
CREATE TABLE IF NOT EXISTS catalog_component (
  id SERIAL PRIMARY KEY,
  key TEXT UNIQUE,
  kind TEXT,
  title TEXT,
  import_path TEXT,
  summary TEXT,
  tags TEXT,
  companions_json TEXT,
  source_scope TEXT,
  source_hash TEXT,
  last_sync_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
)
""",
                    """
CREATE TABLE IF NOT EXISTS catalog_context_contract (
  component_id INTEGER PRIMARY KEY,
  requires_json TEXT,
  provides_json TEXT,
  mutates_json TEXT,
  cache_json TEXT,
  notes_json TEXT,
  artifact_requires_json TEXT,
  artifact_provides_json TEXT,
  phase_in_json TEXT,
  phase_out_json TEXT
)
""",
                    """
CREATE TABLE IF NOT EXISTS catalog_usage_contract (
  component_id INTEGER PRIMARY KEY,
  use_when_json TEXT,
  minimal_wiring_json TEXT,
  required_companions_json TEXT,
  config_keys_json TEXT,
  example_entry TEXT
)
""",
                    """
CREATE TABLE IF NOT EXISTS catalog_param_contract (
  id SERIAL PRIMARY KEY,
  component_id INTEGER,
  name TEXT,
  type TEXT,
  default_value TEXT,
  required BOOLEAN,
  description TEXT,
  source TEXT,
  order_index INTEGER
)
""",
                    """
CREATE TABLE IF NOT EXISTS catalog_method_contract (
  id SERIAL PRIMARY KEY,
  component_id INTEGER,
  name TEXT,
  required BOOLEAN,
  implemented BOOLEAN,
  signature TEXT,
  origin TEXT
)
""",
                    """
CREATE TABLE IF NOT EXISTS catalog_health (
  component_id INTEGER PRIMARY KEY,
  import_ok BOOLEAN,
  context_ok BOOLEAN,
  methods_ok BOOLEAN,
  params_ok BOOLEAN,
  issues_json TEXT,
  last_checked_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
)
""",
                        ),
                    ),
                    (
                        2,
                        (
                            """
CREATE TABLE IF NOT EXISTS catalog_field_value (
  id SERIAL PRIMARY KEY,
  component_id INTEGER NOT NULL,
  field_scope TEXT NOT NULL,
  field_name TEXT NOT NULL,
  field_value TEXT NOT NULL,
  field_value_norm TEXT NOT NULL
)
""",
                            "CREATE INDEX IF NOT EXISTS idx_catalog_field_component ON catalog_field_value (component_id)",
                            "CREATE INDEX IF NOT EXISTS idx_catalog_field_name ON catalog_field_value (field_name)",
                            "CREATE INDEX IF NOT EXISTS idx_catalog_field_name_norm ON catalog_field_value (field_name, field_value_norm)",
                        ),
                    ),
                    (
                        4,
                        (
                            "ALTER TABLE catalog_context_contract ADD COLUMN artifact_requires_json TEXT",
                            "ALTER TABLE catalog_context_contract ADD COLUMN artifact_provides_json TEXT",
                            "ALTER TABLE catalog_context_contract ADD COLUMN phase_in_json TEXT",
                            "ALTER TABLE catalog_context_contract ADD COLUMN phase_out_json TEXT",
                        ),
                    ),
                ]
            )

        for version, statements in migrations:
            if version in applied:
                continue
            for stmt in statements:
                safe_exec(stmt)
            cur.execute(
                "INSERT INTO catalog_schema_migrations (version) VALUES (%s) ON CONFLICT (version) DO NOTHING",
                (int(version),),
            )
            conn.commit()
        cur.close()

    def _ensure_field_value_index(self, conn) -> None:
        cur = conn.cursor()
        try:
            cur.execute("SELECT COUNT(*) AS count FROM catalog_field_value")
            row = cur.fetchone()
            field_value_count = int((row.get("count") if isinstance(row, Mapping) else row[0]) or 0) if row else 0
            if field_value_count > 0:
                return
            cur.execute("SELECT COUNT(*) AS count FROM catalog_component")
            row = cur.fetchone()
            component_count = int((row.get("count") if isinstance(row, Mapping) else row[0]) or 0) if row else 0
            if component_count <= 0:
                return
        finally:
            cur.close()

        cur = conn.cursor()
        cur.execute(
            """
SELECT c.id, c.key, c.kind, c.title, c.import_path, c.summary, c.tags, c.companions_json,
       ctx.requires_json AS context_requires, ctx.provides_json AS context_provides,
       ctx.mutates_json AS context_mutates, ctx.cache_json AS context_cache, ctx.notes_json AS context_notes,
       ctx.artifact_requires_json AS artifact_requires, ctx.artifact_provides_json AS artifact_provides,
       ctx.phase_in_json AS phase_in, ctx.phase_out_json AS phase_out,
       usage_tbl.use_when_json, usage_tbl.minimal_wiring_json, usage_tbl.required_companions_json,
       usage_tbl.config_keys_json, usage_tbl.example_entry
FROM catalog_component AS c
LEFT JOIN catalog_context_contract AS ctx ON c.id = ctx.component_id
LEFT JOIN catalog_usage_contract AS usage_tbl ON c.id = usage_tbl.component_id
"""
        )
        rows = cur.fetchall() or []
        cur.close()

        insert_rows: List[Tuple[int, str, str, str, str]] = []

        def add_rows(component_id: int, field_scope: str, field_name: str, values: object) -> None:
            seen: set[str] = set()
            for raw_value in _normalize_strings(values):
                value = _trim_field_value(raw_value)
                if not value:
                    continue
                norm = value.lower()
                token = f"{field_scope}|{field_name}|{norm}"
                if token in seen:
                    continue
                seen.add(token)
                insert_rows.append((component_id, field_scope, field_name, value, norm))

        for rec in rows:
            component_id = int(rec.get("id", 0) or 0)
            import_path = str(rec.get("import_path", "") or "").strip()
            add_rows(component_id, "base", "key", rec.get("key"))
            add_rows(component_id, "base", "title", rec.get("title"))
            add_rows(component_id, "base", "name", rec.get("title"))
            add_rows(component_id, "base", "kind", rec.get("kind"))
            add_rows(component_id, "base", "import_path", import_path)
            add_rows(component_id, "base", "module", import_path.partition(":")[0].strip())
            add_rows(component_id, "base", "symbol", import_path.partition(":")[2].strip())
            add_rows(component_id, "base", "summary", rec.get("summary"))
            add_rows(component_id, "base", "tags", self._load_json_tuple(rec.get("tags")))
            add_rows(component_id, "base", "companions", self._load_json_tuple(rec.get("companions_json")))
            add_rows(component_id, "context", "context_requires", self._load_json_tuple(rec.get("context_requires")))
            add_rows(component_id, "context", "context_provides", self._load_json_tuple(rec.get("context_provides")))
            add_rows(component_id, "context", "context_mutates", self._load_json_tuple(rec.get("context_mutates")))
            add_rows(component_id, "context", "context_cache", self._load_json_tuple(rec.get("context_cache")))
            add_rows(component_id, "context", "context_notes", self._load_json_tuple(rec.get("context_notes")))
            add_rows(component_id, "context", "artifact_requires", self._load_json_tuple(rec.get("artifact_requires")))
            add_rows(component_id, "context", "artifact_provides", self._load_json_tuple(rec.get("artifact_provides")))
            add_rows(component_id, "context", "phase_in", self._load_json_tuple(rec.get("phase_in")))
            add_rows(component_id, "context", "phase_out", self._load_json_tuple(rec.get("phase_out")))
            add_rows(component_id, "usage", "use_when", self._load_json_tuple(rec.get("use_when_json")))
            add_rows(component_id, "usage", "minimal_wiring", self._load_json_tuple(rec.get("minimal_wiring_json")))
            add_rows(component_id, "usage", "required_companions", self._load_json_tuple(rec.get("required_companions_json")))
            add_rows(component_id, "usage", "config_keys", self._load_json_tuple(rec.get("config_keys_json")))
            add_rows(component_id, "usage", "example_entry", rec.get("example_entry"))

        if insert_rows:
            cur = conn.cursor()
            cur.executemany(
                """
INSERT INTO catalog_field_value
(component_id, field_scope, field_name, field_value, field_value_norm)
VALUES (%s, %s, %s, %s, %s)
""",
                insert_rows,
            )
            conn.commit()
            cur.close()

    def inspect_legacy_cleanup_state(self, *, profile: str | None = None) -> Dict[str, object]:
        profile_key = str(profile or "").strip()
        conn = _connect_postgres(self._cfg)
        try:
            cur = conn.cursor()
            try:
                cur.execute("SELECT current_schema() AS schema_name")
                row = cur.fetchone()
                schema_name = str((row.get("schema_name") if isinstance(row, Mapping) else row[0]) or "public") if row else "public"

                formal_tables: List[Dict[str, object]] = []
                formal_exists = True
                formal_totals: Dict[str, int] = {}
                for table_name in _FORMAL_SURFACE_TABLES:
                    exists = _pg_table_exists(cur, table_name)
                    row_count = _pg_table_row_count(cur, table_name) if exists else 0
                    formal_tables.append({"name": table_name, "exists": bool(exists), "row_count": int(row_count)})
                    formal_totals[table_name] = int(row_count)
                    formal_exists = formal_exists and bool(exists)

                legacy_tables: List[Dict[str, object]] = []
                legacy_present: List[str] = []
                legacy_row_total = 0
                for table_name in _LEGACY_DECOMPOSED_TABLES:
                    exists = _pg_table_exists(cur, table_name)
                    row_count = _pg_table_row_count(cur, table_name) if exists else 0
                    legacy_tables.append({"name": table_name, "exists": bool(exists), "row_count": int(row_count)})
                    if exists:
                        legacy_present.append(str(table_name))
                    legacy_row_total += int(row_count)

                profile_state: Dict[str, object] = {
                    "requested": profile_key or None,
                    "exists": False,
                    "built_at_utc": None,
                    "declared_total": 0,
                    "entry_rows": 0,
                    "scalar_rows": 0,
                }
                surface_profile_count = 0
                if formal_exists:
                    cur.execute("SELECT COUNT(*) AS count FROM catalog_profiles")
                    row = cur.fetchone()
                    surface_profile_count = int((row.get("count") if isinstance(row, Mapping) else row[0]) or 0) if row else 0
                    if profile_key:
                        cur.execute(
                            "SELECT built_at_utc, total FROM catalog_profiles WHERE profile = %s LIMIT 1",
                            (profile_key,),
                        )
                        row = cur.fetchone()
                        if row:
                            profile_state["exists"] = True
                            profile_state["built_at_utc"] = str(row.get("built_at_utc") or "") if isinstance(row, Mapping) else str(row[0] or "")
                            profile_state["declared_total"] = int((row.get("total") if isinstance(row, Mapping) else row[1]) or 0)
                            cur.execute("SELECT COUNT(*) AS count FROM catalog_entries WHERE profile = %s", (profile_key,))
                            row = cur.fetchone()
                            profile_state["entry_rows"] = int((row.get("count") if isinstance(row, Mapping) else row[0]) or 0) if row else 0
                            cur.execute("SELECT COUNT(*) AS count FROM catalog_scalars WHERE profile = %s", (profile_key,))
                            row = cur.fetchone()
                            profile_state["scalar_rows"] = int((row.get("count") if isinstance(row, Mapping) else row[0]) or 0) if row else 0
            finally:
                cur.close()

            formal_surface_ready = bool(formal_exists and formal_totals.get("catalog_profiles", 0) > 0 and formal_totals.get("catalog_entries", 0) > 0)
            profile_ready = bool(profile_state.get("exists")) if profile_key else bool(formal_surface_ready)
            if profile_key and profile_ready:
                profile_ready = int(profile_state.get("entry_rows", 0) or 0) > 0
            legacy_retired = self._legacy_support_retired(conn)

            blockers: List[str] = []
            warnings: List[str] = []
            if not formal_exists:
                missing = [item["name"] for item in formal_tables if not bool(item.get("exists"))]
                blockers.append("formal catalog surface missing: " + ", ".join(str(name) for name in missing))
            if not formal_surface_ready:
                blockers.append("formal catalog surface is empty; materialize a profile before cleanup")
            if profile_key and not bool(profile_state.get("exists")):
                blockers.append(f"formal profile not materialized: {profile_key}")
            elif profile_key and int(profile_state.get("entry_rows", 0) or 0) <= 0:
                blockers.append(f"formal profile has no entry rows: {profile_key}")
            if self._readonly:
                blockers.append("catalog store is readonly; use a writable PostgreSQL target for cleanup")
            if legacy_retired and legacy_present:
                warnings.append("legacy-retired marker already exists; legacy tables are being kept only until explicit cleanup")
            if not legacy_present:
                warnings.append("no legacy PostgreSQL catalog tables detected")

            cleanup_needed = bool(legacy_present)
            can_execute = bool(cleanup_needed and not blockers)
            if can_execute:
                message = "legacy PostgreSQL catalog tables are ready to be removed"
            elif cleanup_needed:
                message = "legacy PostgreSQL catalog tables detected, but cleanup is blocked"
            else:
                message = "legacy PostgreSQL catalog tables are already absent"

            return {
                "backend": self.backend,
                "schema": schema_name,
                "profile": profile_key or None,
                "readonly": bool(self._readonly),
                "legacy_retired": bool(legacy_retired),
                "formal_surface_ready": bool(formal_surface_ready),
                "profile_ready": bool(profile_ready),
                "surface_profile_count": int(surface_profile_count),
                "formal_tables": formal_tables,
                "profile_state": profile_state,
                "legacy_tables": legacy_tables,
                "legacy_tables_present": tuple(legacy_present),
                "legacy_total_rows": int(legacy_row_total),
                "cleanup_needed": bool(cleanup_needed),
                "cleanup_candidates": tuple(legacy_present),
                "can_execute": bool(can_execute),
                "blockers": tuple(blockers),
                "warnings": tuple(warnings),
                "message": message,
            }
        finally:
            conn.close()

    def cleanup_legacy_tables(self, *, profile: str | None = None, execute: bool = False) -> Dict[str, object]:
        plan = dict(self.inspect_legacy_cleanup_state(profile=profile))
        plan["execute_requested"] = bool(execute)
        if not execute:
            plan["executed"] = False
            plan["message"] = "dry-run only; re-run with --execute --yes to drop legacy PostgreSQL catalog tables"
            return plan

        cleanup_candidates = tuple(str(name).strip() for name in (plan.get("cleanup_candidates") or ()) if str(name).strip())
        blockers = tuple(str(item).strip() for item in (plan.get("blockers") or ()) if str(item).strip())
        if blockers:
            raise RuntimeError("Cannot cleanup legacy PostgreSQL catalog tables: " + "; ".join(blockers))
        if self._readonly:
            raise RuntimeError("Catalog store is read-only (NSGABLACK_CATALOG_DB_READONLY=1).")
        if not cleanup_candidates:
            plan["executed"] = False
            plan["message"] = "no legacy PostgreSQL catalog tables were present"
            return plan

        conn = _connect_postgres(self._cfg)
        try:
            self._ensure_migration_table(conn)
            cur = conn.cursor()
            try:
                for table_name in cleanup_candidates:
                    cur.execute(f'DROP TABLE IF EXISTS "{table_name}" CASCADE')
                cur.execute(
                    "INSERT INTO catalog_schema_migrations (version) VALUES (%s) ON CONFLICT (version) DO NOTHING",
                    (int(_LEGACY_RETIRE_MIGRATION_VERSION),),
                )
                conn.commit()
            finally:
                cur.close()
        finally:
            conn.close()

        result = dict(self.inspect_legacy_cleanup_state(profile=profile))
        result["execute_requested"] = True
        result["executed"] = True
        result["dropped_tables"] = cleanup_candidates
        result["message"] = "legacy PostgreSQL catalog tables dropped; future PostgreSQL materialize will stay on the formal surface only"
        return result

    def sync_bundle(self, bundle: CatalogBundle, *, profile: str = "default") -> None:
        if self._readonly:
            raise RuntimeError("Catalog store is read-only (NSGABLACK_CATALOG_DB_READONLY=1).")

        conn = _connect_postgres(self._cfg)
        try:
            self._ensure_schema(conn)
            if self._legacy_support_retired(conn):
                self._materialize_surface_catalog(conn, bundle, profile=profile)
                conn.commit()
                return
            component_ids = self._upsert_components(conn, bundle.components)
            self._upsert_contexts(conn, component_ids, bundle.contexts)
            self._upsert_usages(conn, component_ids, bundle.usages)
            self._replace_field_values(conn, component_ids, bundle.components, bundle.contexts, bundle.usages)
            self._replace_params(conn, component_ids, bundle.params)
            self._replace_methods(conn, component_ids, bundle.methods)
            self._upsert_health(conn, component_ids, bundle.health)
            self._materialize_surface_catalog(conn, bundle, profile=profile)
            conn.commit()
        finally:
            conn.close()

    def _upsert_components(self, conn, components: Sequence[CatalogComponentContract]) -> Dict[str, int]:
        cur = conn.cursor()
        out: Dict[str, int] = {}
        for comp in components:
            cur.execute(
                """
INSERT INTO catalog_component
(key, kind, title, import_path, summary, tags, companions_json, source_scope, source_hash, last_sync_at)
VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
ON CONFLICT (key) DO UPDATE SET
  kind = EXCLUDED.kind,
  title = EXCLUDED.title,
  import_path = EXCLUDED.import_path,
  summary = EXCLUDED.summary,
  tags = EXCLUDED.tags,
  companions_json = EXCLUDED.companions_json,
  source_scope = EXCLUDED.source_scope,
  source_hash = EXCLUDED.source_hash,
  last_sync_at = CURRENT_TIMESTAMP
RETURNING id
""",
                (
                    comp.key,
                    comp.kind,
                    comp.title,
                    comp.import_path,
                    comp.summary,
                    json.dumps(list(comp.tags), ensure_ascii=False),
                    json.dumps(list(comp.companions), ensure_ascii=False),
                    comp.source_scope,
                    comp.source_hash,
                ),
            )
            row = cur.fetchone()
            if row:
                out[comp.key] = int(row["id"] if isinstance(row, Mapping) else row[0])
        cur.close()
        return out

    def _upsert_contexts(self, conn, component_ids: Dict[str, int], contexts: Sequence[ContextContract]) -> None:
        cur = conn.cursor()
        for ctx in contexts:
            cid = component_ids.get(ctx.component_key)
            if cid is None:
                continue
            cur.execute(
                """
INSERT INTO catalog_context_contract
(component_id, requires_json, provides_json, mutates_json, cache_json, notes_json, artifact_requires_json, artifact_provides_json, phase_in_json, phase_out_json)
VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
ON CONFLICT (component_id) DO UPDATE SET
  requires_json = EXCLUDED.requires_json,
  provides_json = EXCLUDED.provides_json,
  mutates_json = EXCLUDED.mutates_json,
  cache_json = EXCLUDED.cache_json,
  notes_json = EXCLUDED.notes_json,
  artifact_requires_json = EXCLUDED.artifact_requires_json,
  artifact_provides_json = EXCLUDED.artifact_provides_json,
  phase_in_json = EXCLUDED.phase_in_json,
  phase_out_json = EXCLUDED.phase_out_json
""",
                (
                    cid,
                    json.dumps(list(ctx.requires), ensure_ascii=False),
                    json.dumps(list(ctx.provides), ensure_ascii=False),
                    json.dumps(list(ctx.mutates), ensure_ascii=False),
                    json.dumps(list(ctx.cache), ensure_ascii=False),
                    json.dumps(list(ctx.notes), ensure_ascii=False),
                    json.dumps(list(ctx.artifact_requires), ensure_ascii=False),
                    json.dumps(list(ctx.artifact_provides), ensure_ascii=False),
                    json.dumps(list(ctx.phase_in), ensure_ascii=False),
                    json.dumps(list(ctx.phase_out), ensure_ascii=False),
                ),
            )
        cur.close()

    def _upsert_usages(self, conn, component_ids: Dict[str, int], usages: Sequence[UsageContract]) -> None:
        cur = conn.cursor()
        for usage in usages:
            cid = component_ids.get(usage.component_key)
            if cid is None:
                continue
            cur.execute(
                """
INSERT INTO catalog_usage_contract
(component_id, use_when_json, minimal_wiring_json, required_companions_json, config_keys_json, example_entry)
VALUES (%s, %s, %s, %s, %s, %s)
ON CONFLICT (component_id) DO UPDATE SET
  use_when_json = EXCLUDED.use_when_json,
  minimal_wiring_json = EXCLUDED.minimal_wiring_json,
  required_companions_json = EXCLUDED.required_companions_json,
  config_keys_json = EXCLUDED.config_keys_json,
  example_entry = EXCLUDED.example_entry
""",
                (
                    cid,
                    json.dumps(list(usage.use_when), ensure_ascii=False),
                    json.dumps(list(usage.minimal_wiring), ensure_ascii=False),
                    json.dumps(list(usage.required_companions), ensure_ascii=False),
                    json.dumps(list(usage.config_keys), ensure_ascii=False),
                    usage.example_entry,
                ),
            )
        cur.close()

    def _replace_field_values(
        self,
        conn,
        component_ids: Dict[str, int],
        components: Sequence[CatalogComponentContract],
        contexts: Sequence[ContextContract],
        usages: Sequence[UsageContract],
    ) -> None:
        cur = conn.cursor()
        ids = list(component_ids.values())
        if ids:
            cur.execute("DELETE FROM catalog_field_value WHERE component_id = ANY(%s)", (ids,))

        context_by_key = {ctx.component_key: ctx for ctx in contexts}
        usage_by_key = {usage.component_key: usage for usage in usages}
        rows: List[Tuple[int, str, str, str, str]] = []

        def add_values(component_id: int, field_scope: str, field_name: str, values: object) -> None:
            seen: set[str] = set()
            for raw_value in _normalize_strings(values):
                value = _trim_field_value(raw_value)
                if not value:
                    continue
                norm = value.lower()
                token = f"{field_scope}|{field_name}|{norm}"
                if token in seen:
                    continue
                seen.add(token)
                rows.append((component_id, field_scope, field_name, value, norm))

        for component in components:
            component_id = component_ids.get(component.key)
            if component_id is None:
                continue
            module_name = str(component.import_path.partition(":")[0] or "").strip()
            symbol_name = str(component.import_path.partition(":")[2] or "").strip()
            add_values(component_id, "base", "key", component.key)
            add_values(component_id, "base", "title", component.title)
            add_values(component_id, "base", "name", component.title)
            add_values(component_id, "base", "kind", component.kind)
            add_values(component_id, "base", "import_path", component.import_path)
            add_values(component_id, "base", "module", module_name)
            add_values(component_id, "base", "symbol", symbol_name)
            add_values(component_id, "base", "tags", component.tags)
            add_values(component_id, "base", "companions", component.companions)
            add_values(component_id, "base", "summary", component.summary)

            context = context_by_key.get(component.key)
            if context is not None:
                add_values(component_id, "context", "context_requires", context.requires)
                add_values(component_id, "context", "context_provides", context.provides)
                add_values(component_id, "context", "context_mutates", context.mutates)
                add_values(component_id, "context", "context_cache", context.cache)
                add_values(component_id, "context", "context_notes", context.notes)

            usage = usage_by_key.get(component.key)
            if usage is not None:
                add_values(component_id, "usage", "use_when", usage.use_when)
                add_values(component_id, "usage", "minimal_wiring", usage.minimal_wiring)
                add_values(component_id, "usage", "required_companions", usage.required_companions)
                add_values(component_id, "usage", "config_keys", usage.config_keys)
                add_values(component_id, "usage", "example_entry", usage.example_entry)

        if rows:
            cur.executemany(
                """
INSERT INTO catalog_field_value
(component_id, field_scope, field_name, field_value, field_value_norm)
VALUES (%s, %s, %s, %s, %s)
""",
                rows,
            )
        cur.close()

    def _replace_params(self, conn, component_ids: Dict[str, int], params: Sequence[ParamContract]) -> None:
        cur = conn.cursor()
        ids = list(component_ids.values())
        if ids:
            cur.execute("DELETE FROM catalog_param_contract WHERE component_id = ANY(%s)", (ids,))
        for p in params:
            cid = component_ids.get(p.component_key)
            if cid is None:
                continue
            cur.execute(
                """
INSERT INTO catalog_param_contract
(component_id, name, type, default_value, required, description, source, order_index)
VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
""",
                (
                    cid,
                    p.name,
                    p.type,
                    p.default,
                    bool(p.required),
                    p.desc,
                    p.source,
                    int(p.order_index),
                ),
            )
        cur.close()

    def _replace_methods(self, conn, component_ids: Dict[str, int], methods: Sequence[MethodContract]) -> None:
        cur = conn.cursor()
        ids = list(component_ids.values())
        if ids:
            cur.execute("DELETE FROM catalog_method_contract WHERE component_id = ANY(%s)", (ids,))
        for m in methods:
            cid = component_ids.get(m.component_key)
            if cid is None:
                continue
            cur.execute(
                """
INSERT INTO catalog_method_contract
(component_id, name, required, implemented, signature, origin)
VALUES (%s, %s, %s, %s, %s, %s)
""",
                (
                    cid,
                    m.name,
                    bool(m.required),
                    bool(m.implemented),
                    m.signature,
                    m.origin,
                ),
            )
        cur.close()

    def _upsert_health(self, conn, component_ids: Dict[str, int], health: Sequence[HealthContract]) -> None:
        cur = conn.cursor()
        for h in health:
            cid = component_ids.get(h.component_key)
            if cid is None:
                continue
            cur.execute(
                """
INSERT INTO catalog_health
(component_id, import_ok, context_ok, methods_ok, params_ok, issues_json, last_checked_at)
VALUES (%s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
ON CONFLICT (component_id) DO UPDATE SET
  import_ok = EXCLUDED.import_ok,
  context_ok = EXCLUDED.context_ok,
  methods_ok = EXCLUDED.methods_ok,
  params_ok = EXCLUDED.params_ok,
  issues_json = EXCLUDED.issues_json,
  last_checked_at = CURRENT_TIMESTAMP
""",
                (
                    cid,
                    bool(h.import_ok),
                    bool(h.context_ok),
                    bool(h.methods_ok),
                    bool(h.params_ok),
                    json.dumps(list(h.issues), ensure_ascii=False),
                ),
            )
        cur.close()

    def _surface_entries_from_bundle(self, bundle: CatalogBundle) -> List[tuple[CatalogEntry, str, str]]:
        context_by_key = {ctx.component_key: ctx for ctx in bundle.contexts}
        usage_by_key = {usage.component_key: usage for usage in bundle.usages}
        out: List[tuple[CatalogEntry, str, str]] = []
        for component in bundle.components:
            context = context_by_key.get(component.key)
            usage = usage_by_key.get(component.key)
            entry = CatalogEntry(
                key=component.key,
                title=component.title,
                kind=component.kind,
                import_path=component.import_path,
                tags=tuple(component.tags),
                summary=component.summary,
                companions=tuple(component.companions),
                context_requires=tuple(context.requires) if context is not None else (),
                context_provides=tuple(context.provides) if context is not None else (),
                context_mutates=tuple(context.mutates) if context is not None else (),
                context_cache=tuple(context.cache) if context is not None else (),
                context_notes=tuple(context.notes) if context is not None else (),
                artifact_requires=tuple(context.artifact_requires) if context is not None else (),
                artifact_provides=tuple(context.artifact_provides) if context is not None else (),
                phase_in=tuple(context.phase_in) if context is not None else (),
                phase_out=tuple(context.phase_out) if context is not None else (),
                use_when=tuple(usage.use_when) if usage is not None else (),
                minimal_wiring=tuple(usage.minimal_wiring) if usage is not None else (),
                required_companions=tuple(usage.required_companions) if usage is not None else (),
                config_keys=tuple(usage.config_keys) if usage is not None else (),
                example_entry=str(usage.example_entry or "") if usage is not None else "",
                detail_ref="",
            )
            out.append((entry, str(component.source_scope or ""), str(component.source_hash or "")))
        return out

    def _materialize_surface_catalog(self, conn, bundle: CatalogBundle, *, profile: str) -> None:
        profile_key = str(profile or "default")
        built_at = _utc_now_iso()
        paired_entries = self._surface_entries_from_bundle(bundle)
        entries = [entry for entry, _, _ in paired_entries]
        summary = _surface_summary(entries, profile=profile_key)
        schema = _surface_schema(entries, profile=profile_key)

        entry_rows: List[tuple[object, ...]] = []
        scalar_rows: List[tuple[object, ...]] = []
        for entry, source_scope, source_hash in paired_entries:
            fields = _entry_to_surface_fields(entry, source_scope=source_scope, source_hash=source_hash)
            relations = _entry_to_relations(entry)
            metadata = {
                "import_path": entry.import_path,
                "source_scope": source_scope,
                "source_hash": source_hash,
            }
            entry_rows.append(
                (
                    profile_key,
                    entry.key,
                    entry.kind,
                    entry.title,
                    "registry",
                    entry.import_path,
                    entry.summary,
                    _json_dumps(list(entry.tags)),
                    _json_dumps(metadata),
                    _json_dumps(fields),
                    _json_dumps(relations),
                    _entry_search_text(entry),
                    built_at,
                )
            )
            for row in _entry_scalar_rows(entry):
                scalar_rows.append(
                    (
                        profile_key,
                        entry.key,
                        str(row["scope"]),
                        str(row["field_name"]),
                        str(row["scalar_value"]),
                    )
                )

        cur = conn.cursor()
        cur.execute("DELETE FROM catalog_profiles WHERE profile = %s", (profile_key,))
        cur.execute("DELETE FROM catalog_entries WHERE profile = %s", (profile_key,))
        cur.execute("DELETE FROM catalog_scalars WHERE profile = %s", (profile_key,))
        cur.execute(
            """
INSERT INTO catalog_profiles (profile, built_at_utc, total, summary_json, schema_json)
VALUES (%s, %s, %s, %s, %s)
""",
            (profile_key, built_at, int(len(entries)), _json_dumps(summary), _json_dumps(schema)),
        )
        if entry_rows:
            cur.executemany(
                """
INSERT INTO catalog_entries
(profile, key, kind, name, source, path, summary, tags_json, metadata_json, fields_json, relations_json, search_text, built_at_utc)
VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
""",
                entry_rows,
            )
        if scalar_rows:
            cur.executemany(
                """
INSERT INTO catalog_scalars
(profile, entry_key, scope, field_name, scalar_value)
VALUES (%s, %s, %s, %s, %s)
""",
                scalar_rows,
            )
        cur.close()

    def _load_json_tuple(self, value: object) -> Tuple[str, ...]:
        if not value:
            return ()
        if isinstance(value, (list, tuple)):
            return tuple(str(item).strip() for item in value if str(item).strip())
        if isinstance(value, str):
            try:
                parsed = json.loads(value)
                if isinstance(parsed, list):
                    return tuple(str(item).strip() for item in parsed if str(item).strip())
            except Exception:
                pass
            text = value.strip()
            return (text,) if text else ()
        return ()

    def _catalog_entry_from_record(self, rec: Mapping[str, object], *, profile: str) -> CatalogEntry | None:
        entry = CatalogEntry(
            key=str(rec.get("key", "") or "").strip(),
            title=str(rec.get("title", "") or "").strip(),
            kind=str(rec.get("kind", "") or "").strip().lower(),
            import_path=str(rec.get("import_path", "") or "").strip(),
            tags=self._load_json_tuple(rec.get("tags")),
            summary=str(rec.get("summary", "") or "").strip(),
            companions=self._load_json_tuple(rec.get("companions")),
            context_requires=self._load_json_tuple(rec.get("context_requires")),
            context_provides=self._load_json_tuple(rec.get("context_provides")),
            context_mutates=self._load_json_tuple(rec.get("context_mutates")),
            context_cache=self._load_json_tuple(rec.get("context_cache")),
            context_notes=self._load_json_tuple(rec.get("context_notes")),
            artifact_requires=self._load_json_tuple(rec.get("artifact_requires")),
            artifact_provides=self._load_json_tuple(rec.get("artifact_provides")),
            phase_in=self._load_json_tuple(rec.get("phase_in")),
            phase_out=self._load_json_tuple(rec.get("phase_out")),
            use_when=self._load_json_tuple(rec.get("use_when")),
            minimal_wiring=self._load_json_tuple(rec.get("minimal_wiring")),
            required_companions=self._load_json_tuple(rec.get("required_companions")),
            config_keys=self._load_json_tuple(rec.get("config_keys")),
            example_entry=str(rec.get("example_entry", "") or "").strip(),
        )
        if not entry.key or not entry.kind or not entry.import_path:
            return None
        return _apply_profile_to_entry(enrich_entry_relation_fields(entry), profile=profile)

    def _surface_row_to_entry(self, row: Mapping[str, object], *, profile: str) -> CatalogEntry | None:
        fields = _json_loads(row.get("fields_json"))
        if not isinstance(fields, dict):
            fields = {}
        metadata = _json_loads(row.get("metadata_json"))
        if not isinstance(metadata, dict):
            metadata = {}
        import_path = str(fields.get("import_path", "") or metadata.get("import_path", "") or row.get("path", "") or "").strip()
        entry = CatalogEntry(
            key=str(row.get("key", "") or "").strip(),
            title=str(fields.get("title", "") or row.get("name", "") or "").strip(),
            kind=str(row.get("kind", "") or fields.get("kind", "") or "").strip().lower(),
            import_path=import_path,
            tags=tuple(str(item).strip() for item in (fields.get("tags", []) or []) if str(item).strip()),
            summary=str(row.get("summary", "") or fields.get("summary", "") or "").strip(),
            companions=tuple(str(item).strip() for item in (fields.get("companions", []) or []) if str(item).strip()),
            context_requires=tuple(str(item).strip() for item in (fields.get("context_requires", []) or []) if str(item).strip()),
            context_provides=tuple(str(item).strip() for item in (fields.get("context_provides", []) or []) if str(item).strip()),
            context_mutates=tuple(str(item).strip() for item in (fields.get("context_mutates", []) or []) if str(item).strip()),
            context_cache=tuple(str(item).strip() for item in (fields.get("context_cache", []) or []) if str(item).strip()),
            context_notes=tuple(str(item).strip() for item in (fields.get("context_notes", []) or []) if str(item).strip()),
            artifact_requires=tuple(str(item).strip() for item in (fields.get("artifact_requires", []) or []) if str(item).strip()),
            artifact_provides=tuple(str(item).strip() for item in (fields.get("artifact_provides", []) or []) if str(item).strip()),
            phase_in=tuple(str(item).strip() for item in (fields.get("phase_in", []) or []) if str(item).strip()),
            phase_out=tuple(str(item).strip() for item in (fields.get("phase_out", []) or []) if str(item).strip()),
            use_when=tuple(str(item).strip() for item in (fields.get("use_when", []) or []) if str(item).strip()),
            minimal_wiring=tuple(str(item).strip() for item in (fields.get("minimal_wiring", []) or []) if str(item).strip()),
            required_companions=tuple(str(item).strip() for item in (fields.get("required_companions", []) or []) if str(item).strip()),
            config_keys=tuple(str(item).strip() for item in (fields.get("config_keys", []) or []) if str(item).strip()),
            example_entry=str(fields.get("example_entry", "") or "").strip(),
            detail_ref=str(fields.get("detail_ref", "") or "").strip(),
        )
        if not entry.key or not entry.kind or not entry.import_path:
            return None
        return _apply_profile_to_entry(enrich_entry_relation_fields(entry), profile=profile)

    def _surface_profile_exists(self, conn, *, profile: str) -> bool:
        cur = conn.cursor()
        cur.execute("SELECT 1 FROM catalog_profiles WHERE profile = %s LIMIT 1", (str(profile),))
        row = cur.fetchone()
        cur.close()
        return bool(row)

    def _surface_row_records(
        self,
        conn,
        *,
        profile: str,
        kind: str | None = None,
        tags: Sequence[str] | None = None,
        field_filters: Mapping[str, object] | Sequence[tuple[str, object]] | None = None,
        query: str = "",
        search_field: str = "all",
        limit: int | None = None,
    ) -> List[Mapping[str, object]]:
        filters = _normalize_field_filters(field_filters)
        normalized_kind = str(kind or "").strip().lower()
        normalized_field = str(search_field or "all").strip().lower()
        if normalized_field not in {"all", "name", "tag", "context", "usage"}:
            normalized_field = "all"

        clauses = ["e.profile = %s"]
        params: List[object] = [str(profile)]
        if normalized_kind:
            clauses.append("e.kind = %s")
            params.append(normalized_kind)

        for tag in _normalize_strings(tags):
            clauses.append(
                "EXISTS (SELECT 1 FROM catalog_scalars s_tag "
                "WHERE s_tag.profile = e.profile AND s_tag.entry_key = e.key "
                "AND s_tag.field_name = %s AND LOWER(s_tag.scalar_value) = %s)"
            )
            params.extend(["tags", str(tag).strip().lower()])

        for field_name, values in filters.items():
            if not values:
                continue
            placeholders = ", ".join(["%s"] * len(values))
            clauses.append(
                "EXISTS (SELECT 1 FROM catalog_scalars s_filter "
                "WHERE s_filter.profile = e.profile AND s_filter.entry_key = e.key "
                "AND s_filter.field_name = %s "
                f"AND LOWER(s_filter.scalar_value) IN ({placeholders}))"
            )
            params.append(str(field_name))
            params.extend(str(value).strip().lower() for value in values)

        raw_query = str(query or "").strip().lower()
        tokens = [token for token in raw_query.split() if token]
        for token_group in _expand_token_groups(tokens):
            alias_clauses: List[str] = []
            local_params: List[object] = []
            for alias in token_group:
                pattern = _like_pattern(alias)
                if normalized_field == "name":
                    alias_clauses.append("(LOWER(e.key) LIKE %s OR LOWER(e.name) LIKE %s)")
                    local_params.extend([pattern, pattern])
                elif normalized_field == "tag":
                    alias_clauses.append(
                        "EXISTS (SELECT 1 FROM catalog_scalars s_search "
                        "WHERE s_search.profile = e.profile AND s_search.entry_key = e.key "
                        "AND s_search.field_name = 'tags' AND LOWER(s_search.scalar_value) LIKE %s)"
                    )
                    local_params.append(pattern)
                elif normalized_field == "context":
                    placeholders = ", ".join(["%s"] * len(_CONTEXT_FIELD_NAMES))
                    alias_clauses.append(
                        "EXISTS (SELECT 1 FROM catalog_scalars s_search "
                        "WHERE s_search.profile = e.profile AND s_search.entry_key = e.key "
                        f"AND s_search.field_name IN ({placeholders}) AND LOWER(s_search.scalar_value) LIKE %s)"
                    )
                    local_params.extend([*_CONTEXT_FIELD_NAMES, pattern])
                elif normalized_field == "usage":
                    placeholders = ", ".join(["%s"] * len(_USAGE_FIELD_NAMES))
                    alias_clauses.append(
                        "EXISTS (SELECT 1 FROM catalog_scalars s_search "
                        "WHERE s_search.profile = e.profile AND s_search.entry_key = e.key "
                        f"AND s_search.field_name IN ({placeholders}) AND LOWER(s_search.scalar_value) LIKE %s)"
                    )
                    local_params.extend([*_USAGE_FIELD_NAMES, pattern])
                else:
                    alias_clauses.append("LOWER(e.search_text) LIKE %s")
                    local_params.append(pattern)
            if alias_clauses:
                clauses.append("(" + " OR ".join(alias_clauses) + ")")
                params.extend(local_params)

        sql = (
            "SELECT e.profile, e.key, e.kind, e.name, e.source, e.path, e.summary, e.tags_json, "
            "e.metadata_json, e.fields_json, e.relations_json, e.search_text, e.built_at_utc "
            "FROM catalog_entries e WHERE " + " AND ".join(clauses) + " ORDER BY e.kind ASC, e.key ASC"
        )
        if limit is not None:
            sql += f" LIMIT {max(0, int(limit))}"
        cur = conn.cursor()
        cur.execute(sql, tuple(params))
        rows = cur.fetchall() or []
        cur.close()
        return list(rows)

    def _surface_entries_from_query(
        self,
        conn,
        *,
        profile: str,
        kind: str | None = None,
        tags: Sequence[str] | None = None,
        field_filters: Mapping[str, object] | Sequence[tuple[str, object]] | None = None,
        query: str = "",
        search_field: str = "all",
        limit: int | None = None,
    ) -> List[CatalogEntry]:
        rows = self._surface_row_records(
            conn,
            profile=profile,
            kind=kind,
            tags=tags,
            field_filters=field_filters,
            query=query,
            search_field=search_field,
            limit=limit,
        )
        entries: List[CatalogEntry] = []
        for row in rows:
            entry = self._surface_row_to_entry(row, profile=profile)
            if entry is not None:
                entries.append(entry)
        return _sort_catalog_entries(entries)

    def _catalog_row_records(
        self,
        conn,
        *,
        profile: str,
        kind: str | None = None,
        tags: Sequence[str] | None = None,
        field_filters: Mapping[str, object] | Sequence[tuple[str, object]] | None = None,
        query: str = "",
        search_field: str = "all",
    ) -> List[Mapping[str, object]]:
        filters = _normalize_field_filters(field_filters)
        normalized_kind = str(kind or "").strip().lower()
        normalized_field = str(search_field or "all").strip().lower()
        if normalized_field not in {"all", "name", "tag", "context", "usage"}:
            normalized_field = "all"

        clauses = ["1=1"]
        params: List[object] = []
        profile_clause, profile_params = _profile_sql_filters(profile)
        if profile_clause:
            clauses.append(profile_clause)
            params.extend(profile_params)
        if normalized_kind:
            clauses.append("c.kind = %s")
            params.append(normalized_kind)

        for tag in _normalize_strings(tags):
            clauses.append(
                "EXISTS (SELECT 1 FROM catalog_field_value fv_tag "
                "WHERE fv_tag.component_id = c.id AND fv_tag.field_name = %s AND fv_tag.field_value_norm = %s)"
            )
            params.extend(["tags", str(tag).strip().lower()])

        for field_name, values in filters.items():
            if not values:
                continue
            placeholders = ", ".join(["%s"] * len(values))
            clauses.append(
                "EXISTS (SELECT 1 FROM catalog_field_value fv_filter "
                "WHERE fv_filter.component_id = c.id AND fv_filter.field_name = %s "
                f"AND fv_filter.field_value_norm IN ({placeholders}))"
            )
            params.append(str(field_name))
            params.extend(str(value).strip().lower() for value in values)

        raw_query = str(query or "").strip().lower()
        tokens = [token for token in raw_query.split() if token]
        for token_group in _expand_token_groups(tokens):
            alias_clauses: List[str] = []
            for alias in token_group:
                pattern = _like_pattern(alias)
                if normalized_field == "name":
                    alias_clauses.append("(LOWER(c.key) LIKE %s OR LOWER(c.title) LIKE %s)")
                    params.extend([pattern, pattern])
                elif normalized_field == "tag":
                    alias_clauses.append(
                        "EXISTS (SELECT 1 FROM catalog_field_value fv_search "
                        "WHERE fv_search.component_id = c.id AND fv_search.field_name = 'tags' "
                        "AND fv_search.field_value_norm LIKE %s)"
                    )
                    params.append(pattern)
                elif normalized_field == "context":
                    placeholders = ", ".join(["%s"] * len(_CONTEXT_FIELD_NAMES))
                    alias_clauses.append(
                        "EXISTS (SELECT 1 FROM catalog_field_value fv_search "
                        "WHERE fv_search.component_id = c.id "
                        f"AND fv_search.field_name IN ({placeholders}) "
                        "AND fv_search.field_value_norm LIKE %s)"
                    )
                    params.extend(list(_CONTEXT_FIELD_NAMES) + [pattern])
                elif normalized_field == "usage":
                    placeholders = ", ".join(["%s"] * len(_USAGE_FIELD_NAMES))
                    alias_clauses.append(
                        "EXISTS (SELECT 1 FROM catalog_field_value fv_search "
                        "WHERE fv_search.component_id = c.id "
                        f"AND fv_search.field_name IN ({placeholders}) "
                        "AND fv_search.field_value_norm LIKE %s)"
                    )
                    params.extend(list(_USAGE_FIELD_NAMES) + [pattern])
                else:
                    alias_clauses.append(
                        "("
                        "LOWER(c.key) LIKE %s OR LOWER(c.title) LIKE %s OR LOWER(c.kind) LIKE %s "
                        "OR LOWER(c.import_path) LIKE %s OR LOWER(c.summary) LIKE %s "
                        "OR EXISTS (SELECT 1 FROM catalog_field_value fv_search "
                        "WHERE fv_search.component_id = c.id AND fv_search.field_name IN ("
                        + ", ".join(["%s"] * len(_SEARCHABLE_FIELD_NAMES))
                        + ") AND fv_search.field_value_norm LIKE %s)"
                        ")"
                    )
                    params.extend([pattern, pattern, pattern, pattern, pattern, *_SEARCHABLE_FIELD_NAMES, pattern])
            if alias_clauses:
                clauses.append("(" + " OR ".join(alias_clauses) + ")")

        cur = conn.cursor()
        cur.execute(
            """
SELECT c.id, c.key, c.kind, c.title, c.import_path, c.summary, c.tags, c.companions_json,
       ctx.requires_json AS context_requires, ctx.provides_json AS context_provides,
       ctx.mutates_json AS context_mutates, ctx.cache_json AS context_cache, ctx.notes_json AS context_notes,
       ctx.artifact_requires_json AS artifact_requires, ctx.artifact_provides_json AS artifact_provides,
       ctx.phase_in_json AS phase_in, ctx.phase_out_json AS phase_out,
       usage_tbl.use_when_json, usage_tbl.minimal_wiring_json, usage_tbl.required_companions_json,
       usage_tbl.config_keys_json, usage_tbl.example_entry
FROM catalog_component AS c
LEFT JOIN catalog_context_contract AS ctx ON c.id = ctx.component_id
LEFT JOIN catalog_usage_contract AS usage_tbl ON c.id = usage_tbl.component_id
WHERE """
            + " AND ".join(clauses),
            tuple(params),
        )
        rows = cur.fetchall() or []
        cur.close()
        records: List[Mapping[str, object]] = []
        for rec in rows:
            records.append(
                {
                    "id": rec.get("id"),
                    "key": rec.get("key"),
                    "kind": rec.get("kind"),
                    "title": rec.get("title"),
                    "import_path": rec.get("import_path"),
                    "summary": rec.get("summary"),
                    "tags": rec.get("tags"),
                    "companions": rec.get("companions_json"),
                    "context_requires": rec.get("context_requires"),
                    "context_provides": rec.get("context_provides"),
                    "context_mutates": rec.get("context_mutates"),
                    "context_cache": rec.get("context_cache"),
                    "context_notes": rec.get("context_notes"),
                    "artifact_requires": rec.get("artifact_requires"),
                    "artifact_provides": rec.get("artifact_provides"),
                    "phase_in": rec.get("phase_in"),
                    "phase_out": rec.get("phase_out"),
                    "use_when": rec.get("use_when_json"),
                    "minimal_wiring": rec.get("minimal_wiring_json"),
                    "required_companions": rec.get("required_companions_json"),
                    "config_keys": rec.get("config_keys_json"),
                    "example_entry": rec.get("example_entry"),
                }
            )
        return records

    def _catalog_entries_from_query(
        self,
        conn,
        *,
        profile: str,
        kind: str | None = None,
        tags: Sequence[str] | None = None,
        field_filters: Mapping[str, object] | Sequence[tuple[str, object]] | None = None,
        query: str = "",
        search_field: str = "all",
    ) -> List[CatalogEntry]:
        records = self._catalog_row_records(
            conn,
            profile=profile,
            kind=kind,
            tags=tags,
            field_filters=field_filters,
            query=query,
            search_field=search_field,
        )
        entries: List[CatalogEntry] = []
        for rec in records:
            entry = self._catalog_entry_from_record(rec, profile=profile)
            if entry is not None:
                entries.append(entry)
        return _sort_catalog_entries(entries)

    def list_catalog_entries(
        self,
        *,
        profile: str = "default",
        kind: str | None = None,
        tags: Sequence[str] | None = None,
        limit: int | None = None,
        field_filters: Mapping[str, object] | Sequence[tuple[str, object]] | None = None,
    ) -> List[CatalogEntry]:
        conn = _connect_postgres(self._cfg)
        try:
            self._ensure_schema(conn)
            if self._surface_profile_exists(conn, profile=profile):
                entries = self._surface_entries_from_query(
                    conn,
                    profile=profile,
                    kind=kind,
                    tags=tags,
                    field_filters=field_filters,
                    limit=limit,
                )
                return entries if limit is None else entries[: max(0, int(limit))]
            if not self._legacy_query_tables_available(conn):
                return []
            entries = self._catalog_entries_from_query(conn, profile=profile, kind=kind, tags=tags, field_filters=field_filters)
            return entries if limit is None else entries[: max(0, int(limit))]
        finally:
            conn.close()

    def search_catalog_entries(
        self,
        query: str,
        *,
        profile: str = "default",
        kind: str | None = None,
        tags: Sequence[str] | None = None,
        field: str = "all",
        limit: int = 20,
        field_filters: Mapping[str, object] | Sequence[tuple[str, object]] | None = None,
    ) -> List[CatalogEntry]:
        text = str(query or "").strip()
        if not text:
            return self.list_catalog_entries(
                profile=profile,
                kind=kind,
                tags=tags,
                limit=limit,
                field_filters=field_filters,
            )
        conn = _connect_postgres(self._cfg)
        try:
            self._ensure_schema(conn)
            if self._surface_profile_exists(conn, profile=profile):
                return self._surface_entries_from_query(
                    conn,
                    profile=profile,
                    kind=kind,
                    tags=tags,
                    field_filters=field_filters,
                    query=text,
                    search_field=field,
                    limit=limit,
                )[: max(0, int(limit))]
            if not self._legacy_query_tables_available(conn):
                return []
            entries = self._catalog_entries_from_query(
                conn,
                profile=profile,
                kind=kind,
                tags=tags,
                field_filters=field_filters,
                query=text,
                search_field=field,
            )
            return entries[: max(0, int(limit))]
        finally:
            conn.close()

    def get_catalog_entry(self, key: str, *, profile: str = "default") -> Optional[CatalogEntry]:
        normalized_key = str(key or "").strip()
        if not normalized_key:
            return None
        conn = _connect_postgres(self._cfg)
        try:
            self._ensure_schema(conn)
            if self._surface_profile_exists(conn, profile=profile):
                rows = self._surface_row_records(conn, profile=profile, field_filters={"key": (normalized_key,)}, limit=10)
                for row in rows:
                    if str(row.get("key", "") or "").strip() != normalized_key:
                        continue
                    return self._surface_row_to_entry(row, profile=profile)
                return None
            if not self._legacy_query_tables_available(conn):
                return None
            records = self._catalog_row_records(conn, profile=profile, field_filters={"key": (normalized_key,)})
            for rec in records:
                if str(rec.get("key", "") or "").strip() != normalized_key:
                    continue
                return self._catalog_entry_from_record(rec, profile=profile)
            return None
        finally:
            conn.close()

    def field_values(
        self,
        field_name: str,
        *,
        profile: str = "default",
        kind: str | None = None,
        query: str = "",
        search_field: str = "all",
        limit: int = 100,
        field_filters: Mapping[str, object] | Sequence[tuple[str, object]] | None = None,
    ) -> List[Dict[str, object]]:
        target_field = str(field_name or "").strip()
        if not target_field:
            return []
        conn = _connect_postgres(self._cfg)
        try:
            self._ensure_schema(conn)
            if self._surface_profile_exists(conn, profile=profile):
                entries = self._surface_entries_from_query(
                    conn,
                    profile=profile,
                    kind=kind,
                    field_filters=field_filters,
                    query=query,
                    search_field=search_field,
                    limit=None,
                )
            else:
                if not self._legacy_query_tables_available(conn):
                    return []
                entries = self._catalog_entries_from_query(
                    conn,
                    profile=profile,
                    kind=kind,
                    field_filters=field_filters,
                    query=query,
                    search_field=search_field,
                )
            counter: Dict[str, int] = {}
            for entry in entries:
                if target_field == "key":
                    values = (entry.key,)
                elif target_field in {"title", "name"}:
                    values = (entry.title,)
                elif target_field == "kind":
                    values = (entry.kind,)
                elif target_field == "import_path":
                    values = (entry.import_path,)
                elif target_field == "module":
                    values = (entry.import_path.partition(":")[0].strip(),) if entry.import_path else ()
                elif target_field == "symbol":
                    symbol_name = entry.import_path.partition(":")[2].strip()
                    values = (symbol_name,) if symbol_name else ()
                elif target_field == "summary":
                    values = (entry.summary,) if entry.summary else ()
                else:
                    values = tuple(getattr(entry, target_field, ()) or ())
                for value in values:
                    text = str(value).strip()
                    if not text:
                        continue
                    counter[text] = int(counter.get(text, 0) + 1)
            rows = sorted(counter.items(), key=lambda item: (-item[1], item[0].lower()))
            return [{"value": value, "count": count} for value, count in rows[: max(0, int(limit))]]
        finally:
            conn.close()

    def facet_rows(
        self,
        *,
        profile: str = "default",
        kind: str | None = None,
        query: str = "",
        search_field: str = "all",
        field_filters: Mapping[str, object] | Sequence[tuple[str, object]] | None = None,
        fields: Sequence[str] | None = None,
        limit_per_field: int = 25,
    ) -> Dict[str, List[Dict[str, object]]]:
        target_fields = tuple(str(field).strip() for field in tuple(fields or ()) if str(field).strip())
        if not target_fields:
            return {}
        payload: Dict[str, List[Dict[str, object]]] = {}
        for field_name in target_fields:
            payload[str(field_name)] = self.field_values(
                field_name,
                profile=profile,
                kind=kind,
                query=query,
                search_field=search_field,
                limit=limit_per_field,
                field_filters=field_filters,
            )
        return payload

    def neighbor_payload(self, key: str, *, profile: str = "default") -> Optional[Dict[str, object]]:
        entry = self.get_catalog_entry(key, profile=profile)
        if entry is None:
            return None
        all_entries = [item for item in self.list_catalog_entries(profile=profile, limit=None) if item.key != entry.key]
        entry_by_key = {item.key: item for item in all_entries}
        companion_entries = [entry_by_key[companion_key] for companion_key in entry.companions if companion_key in entry_by_key]
        companions_by_key = {item.key: item for item in companion_entries}
        companions = [{"key": item.key, "title": item.title, "kind": item.kind, "summary": item.summary} for item in companion_entries]
        missing_companions = tuple(companion_key for companion_key in entry.companions if companion_key not in companions_by_key)
        linked_by_entries = [item for item in all_entries if entry.key in tuple(item.companions or ())]
        linked_by = [{"key": item.key, "title": item.title, "kind": item.kind, "summary": item.summary} for item in linked_by_entries]
        contract_sections = build_contract_neighbor_sections(entry, candidates=all_entries)
        return {
            "key": entry.key,
            "companions": companions,
            "missing_companions": missing_companions,
            "linked_by": linked_by,
            **contract_sections,
        }
