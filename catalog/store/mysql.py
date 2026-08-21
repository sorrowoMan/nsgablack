from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple
from urllib.parse import urlparse
from pathlib import Path

try:  # py>=3.11
    import tomllib as _toml
except Exception:  # pragma: no cover
    try:  # py<3.11
        import tomli as _toml  # type: ignore[import-not-found]
    except Exception:  # pragma: no cover
        _toml = None

from ..contracts import (
    ApiIndexEntry,
    ApiIndexMeta,
    ApiDocEntry,
    ApiDocGap,
    CatalogBundle,
    CatalogComponentContract,
    CatalogContextContract,
    HealthContract,
    MethodContract,
    ParamContract,
    UsageContract,
)
from ..contract_relations import build_contract_neighbor_sections, enrich_entry_relation_fields
from ..registry import CatalogEntry, _expand_token_groups, _normalize_catalog_profile


_MYSQL_CHARSET = "utf8mb4"
_MYSQL_COLLATION = "utf8mb4_unicode_ci"
_FIELD_VALUE_LIMIT = 512
_FRAMEWORK_CORE_EXCLUDED_KINDS = ("example", "doc")
_FRAMEWORK_CORE_EXCLUDED_IMPORT_PATTERNS = (
    "%examples/%",
    "%examples\\%",
)
_CONTEXT_FIELD_NAMES = (
    "context_requires",
    "context_provides",
    "context_mutates",
    "context_cache",
    "context_notes",
    "artifact_requires",
    "artifact_provides",
    "phase_in",
    "phase_out",
)
_USAGE_FIELD_NAMES = (
    "use_when",
    "minimal_wiring",
    "required_companions",
    "config_keys",
    "example_entry",
)
_SEARCHABLE_FIELD_NAMES = (
    "tags",
    "companions",
    "module",
    "symbol",
    *_CONTEXT_FIELD_NAMES,
    *_USAGE_FIELD_NAMES,
)


def _apply_connection_charset(conn) -> None:
    try:
        cur = conn.cursor()
    except Exception:
        return
    try:
        cur.execute(f"SET NAMES {_MYSQL_CHARSET} COLLATE {_MYSQL_COLLATION}")
        cur.execute(f"SET collation_connection = '{_MYSQL_COLLATION}'")
    except Exception:
        pass
    finally:
        try:
            cur.close()
        except Exception:
            pass


def _truthy_env(name: str) -> bool:
    value = os.environ.get(name, "").strip().lower()
    return value in {"1", "true", "yes", "on"}


def _env_url_uses_mysql(url: str) -> bool:
    raw = str(url or "").strip()
    if not raw:
        return False
    try:
        scheme = str(urlparse(raw).scheme or "").strip().lower()
    except Exception:
        return False
    return scheme in {"mysql", "mysql+pymysql", "mysql+mysqlconnector"}


def _read_mysql_config_file() -> Dict[str, object]:
    if _toml is None:
        return {}
    env_path = os.environ.get("NSGABLACK_CATALOG_DB_CONFIG", "").strip()
    candidates: List[Path] = []
    if env_path:
        candidates.append(Path(env_path))
    candidates.append(Path.cwd() / "catalog" / "db.toml")
    candidates.append(Path(__file__).resolve().parent.parent / "db.toml")
    for path in candidates:
        if not path.exists() or not path.is_file():
            continue
        try:
            data = _toml.loads(path.read_text(encoding="utf-8", errors="replace"))
        except Exception:
            continue
        if isinstance(data, dict):
            return data
    return {}


def _resolve_mysql_config() -> tuple[Optional[str], Optional[MySQLCatalogConfig], bool]:
    env_url = os.environ.get("NSGABLACK_CATALOG_DB_URL", "").strip()
    if _env_url_uses_mysql(env_url):
        return env_url, parse_mysql_url(env_url), _truthy_env("NSGABLACK_CATALOG_DB_READONLY")

    cfg_data = _read_mysql_config_file()
    mysql_block = cfg_data.get("mysql") if isinstance(cfg_data, dict) else None
    if not isinstance(mysql_block, dict):
        mysql_block = {}
    enabled = bool(mysql_block.get("enabled", False))
    if not enabled:
        return None, None, False

    url = str(mysql_block.get("url", "") or "").strip()
    if url:
        readonly = bool(mysql_block.get("readonly", False))
        return url, parse_mysql_url(url), readonly

    cfg = MySQLCatalogConfig(
        host=str(mysql_block.get("host", "127.0.0.1")),
        port=int(mysql_block.get("port", 3306)),
        user=str(mysql_block.get("user", "root")),
        password=str(mysql_block.get("password", "")),
        database=str(mysql_block.get("database", "nsgablack")),
        connect_timeout=int(mysql_block.get("connect_timeout", 10)),
    )
    readonly = bool(mysql_block.get("readonly", False))
    return None, cfg, readonly


def mysql_config_enabled() -> bool:
    env_url = os.environ.get("NSGABLACK_CATALOG_DB_URL", "").strip()
    if _env_url_uses_mysql(env_url):
        return True
    cfg_data = _read_mysql_config_file()
    mysql_block = cfg_data.get("mysql") if isinstance(cfg_data, dict) else None
    if not isinstance(mysql_block, dict):
        return False
    return bool(mysql_block.get("enabled", False))


def mysql_config_mode() -> str:
    env_mode = os.environ.get("NSGABLACK_CATALOG_DB_MODE", "").strip().lower()
    if env_mode in {"only", "prefer", "off", "disabled"}:
        return "off" if env_mode == "disabled" else env_mode
    cfg_data = _read_mysql_config_file()
    mysql_block = cfg_data.get("mysql") if isinstance(cfg_data, dict) else None
    if isinstance(mysql_block, dict):
        mode = str(mysql_block.get("mode", "") or "").strip().lower()
        if mode in {"only", "prefer", "off", "disabled"}:
            return "off" if mode == "disabled" else mode
    return "prefer"


def mysql_config_info() -> Dict[str, object]:
    env_url = os.environ.get("NSGABLACK_CATALOG_DB_URL", "").strip()
    env_cfg = os.environ.get("NSGABLACK_CATALOG_DB_CONFIG", "").strip()
    data = _read_mysql_config_file()
    mysql_block = data.get("mysql") if isinstance(data, dict) else None
    if not isinstance(mysql_block, dict):
        mysql_block = {}
    return {
        "enabled": mysql_config_enabled(),
        "mode": mysql_config_mode(),
        "config_env": env_cfg or None,
        "explicit_url_env": _env_url_uses_mysql(env_url),
        "readonly": bool(mysql_block.get("readonly", False)) or _truthy_env("NSGABLACK_CATALOG_DB_READONLY"),
    }


def _normalize_strings(values: object) -> Tuple[str, ...]:
    if values is None:
        return ()
    if isinstance(values, str):
        text = values.strip()
        return (text,) if text else ()
    if isinstance(values, Mapping):
        out: List[str] = []
        for key in values.keys():
            text = str(key).strip()
            if text:
                out.append(text)
        return tuple(out)
    if isinstance(values, (list, tuple, set, frozenset)):
        out: List[str] = []
        for item in values:
            out.extend(_normalize_strings(item))
        return tuple(out)
    text = str(values).strip()
    return (text,) if text else ()


def _normalize_field_filters(
    field_filters: Mapping[str, object] | Sequence[tuple[str, object]] | None,
) -> Dict[str, Tuple[str, ...]]:
    if not field_filters:
        return {}
    items = field_filters.items() if isinstance(field_filters, Mapping) else field_filters
    out: Dict[str, Tuple[str, ...]] = {}
    for name, value in items:
        key = str(name or "").strip()
        if not key:
            continue
        values = tuple(item for item in _normalize_strings(value) if item)
        if values:
            out[key] = values
    return out


def _trim_field_value(value: object) -> str:
    text = str(value or "").strip()
    if len(text) <= _FIELD_VALUE_LIMIT:
        return text
    return text[: _FIELD_VALUE_LIMIT]


def _entry_uses_examples_path(text: object) -> bool:
    raw = str(text or "").lower()
    return "examples/" in raw or "examples\\" in raw


def _apply_profile_to_entry(entry: CatalogEntry, *, profile: str) -> CatalogEntry | None:
    profile_key = _normalize_catalog_profile(profile)
    if profile_key != "framework-core":
        return entry
    if entry.kind in _FRAMEWORK_CORE_EXCLUDED_KINDS:
        return None
    if _entry_uses_examples_path(entry.import_path):
        return None
    if _entry_uses_examples_path(entry.example_entry):
        entry = CatalogEntry(
            key=entry.key,
            title=entry.title,
            kind=entry.kind,
            import_path=entry.import_path,
            tags=entry.tags,
            summary=entry.summary,
            companions=entry.companions,
            context_requires=entry.context_requires,
            context_provides=entry.context_provides,
            context_mutates=entry.context_mutates,
            context_cache=entry.context_cache,
            context_notes=entry.context_notes,
            use_when=entry.use_when,
            minimal_wiring=entry.minimal_wiring,
            required_companions=entry.required_companions,
            config_keys=entry.config_keys,
            example_entry="",
            detail_ref=entry.detail_ref,
        )
    return entry


def _profile_sql_filters(profile: str) -> tuple[str, List[object]]:
    profile_key = _normalize_catalog_profile(profile)
    if profile_key != "framework-core":
        return "", []
    clauses = [
        "c.kind NOT IN (%s, %s)",
        "LOWER(c.import_path) NOT LIKE %s",
        "LOWER(c.import_path) NOT LIKE %s",
    ]
    params: List[object] = [
        _FRAMEWORK_CORE_EXCLUDED_KINDS[0],
        _FRAMEWORK_CORE_EXCLUDED_KINDS[1],
        *_FRAMEWORK_CORE_EXCLUDED_IMPORT_PATTERNS,
    ]
    return " AND ".join(clauses), params


def _like_pattern(token: str) -> str:
    return f"%{str(token or '').strip().lower()}%"


def _catalog_kind_rank(kind: str) -> int:
    order = {
        "adapter": 0,
        "plugin": 1,
        "bias": 2,
        "representation": 3,
        "suite": 4,
        "tool": 5,
        "doc": 6,
        "example": 7,
    }
    return int(order.get(str(kind or "").strip().lower(), 99))


def _sort_catalog_entries(entries: Sequence[CatalogEntry]) -> List[CatalogEntry]:
    return sorted(entries, key=lambda entry: (_catalog_kind_rank(entry.kind), entry.key))


@dataclass(frozen=True)
class MySQLCatalogConfig:
    host: str
    port: int
    user: str
    password: str
    database: str
    connect_timeout: int = 10


def parse_mysql_url(url: str) -> MySQLCatalogConfig:
    parsed = urlparse(url)
    if parsed.scheme not in {"mysql", "mysql+pymysql", "mysql+mysqlconnector"}:
        raise ValueError(f"Unsupported MySQL URL scheme: {parsed.scheme}")
    host = parsed.hostname or "127.0.0.1"
    port = int(parsed.port or 3306)
    user = parsed.username or "root"
    password = parsed.password or ""
    database = (parsed.path or "").lstrip("/") or "nsgablack"
    return MySQLCatalogConfig(
        host=host,
        port=port,
        user=user,
        password=password,
        database=database,
    )


def _connect_mysql(cfg: MySQLCatalogConfig):
    try:
        import mysql.connector as mysql_connector  # type: ignore
    except Exception:
        mysql_connector = None

    if mysql_connector is not None:
        common_kwargs = {
            "host": cfg.host,
            "port": int(cfg.port),
            "user": cfg.user,
            "password": cfg.password,
            "database": cfg.database,
            "connection_timeout": int(cfg.connect_timeout),
            "charset": _MYSQL_CHARSET,
            "use_unicode": True,
        }
        # The canonical connection form deliberately omits ``collation``:
        # older connector releases accept the remaining kwargs, and the next
        # line applies the authoritative charset/collation once connected.
        conn = mysql_connector.connect(**common_kwargs)
        _apply_connection_charset(conn)
        return conn

    try:
        import pymysql  # type: ignore
    except Exception as exc:
        raise RuntimeError("MySQL driver missing: install mysql-connector-python or pymysql.") from exc

    conn = pymysql.connect(
        host=cfg.host,
        port=int(cfg.port),
        user=cfg.user,
        password=cfg.password,
        database=cfg.database,
        connect_timeout=int(cfg.connect_timeout),
        charset=_MYSQL_CHARSET,
        use_unicode=True,
    )
    _apply_connection_charset(conn)
    return conn


class MySQLCatalogStore:
    backend = "mysql"

    def __init__(self, url: Optional[str] = None, *, readonly: Optional[bool] = None) -> None:
        cfg: Optional[MySQLCatalogConfig] = None
        resolved_url: Optional[str] = None
        resolved_readonly = False
        if url:
            resolved_url = url
            cfg = parse_mysql_url(url)
        else:
            resolved_url, cfg, resolved_readonly = _resolve_mysql_config()
        if cfg is None and resolved_url:
            cfg = parse_mysql_url(resolved_url)
        if cfg is None:
            raise RuntimeError(
                "MySQL catalog config missing. Set NSGABLACK_CATALOG_DB_URL or enable catalog/db.toml."
            )
        self._url = resolved_url or ""
        self._cfg = cfg
        if readonly is not None:
            self._readonly = bool(readonly)
        else:
            self._readonly = bool(resolved_readonly)

    @property
    def readonly(self) -> bool:
        return self._readonly

    def _ensure_schema(self, conn) -> None:
        self._apply_migrations(conn)
        self._ensure_field_value_index(conn)

    def _apply_migrations(self, conn) -> None:
        cur = conn.cursor()
        cur.execute(
            """
CREATE TABLE IF NOT EXISTS catalog_schema_migrations (
  version INT PRIMARY KEY,
  applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
"""
        )
        conn.commit()

        cur.execute("SELECT version FROM catalog_schema_migrations")
        rows = cur.fetchall() or []
        applied = set()
        for row in rows:
            if isinstance(row, dict):
                applied.add(int(row.get("version", 0)))
            else:
                applied.add(int(row[0]))

        def safe_exec(stmt: str) -> None:
            try:
                cur.execute(stmt)
            except Exception as exc:
                msg = str(exc).lower()
                if "duplicate" in msg or "already exists" in msg:
                    return
                raise

        migrations: List[tuple[int, Sequence[str]]] = [
            (
                1,
                (
                    """
CREATE TABLE IF NOT EXISTS catalog_component (
  id INT AUTO_INCREMENT PRIMARY KEY,
  `key` VARCHAR(128) UNIQUE,
  kind VARCHAR(32),
  title VARCHAR(256),
  import_path VARCHAR(256),
  summary TEXT,
  tags TEXT,
  companions_json TEXT,
  source_scope VARCHAR(32),
  source_hash VARCHAR(64),
  last_sync_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
)
""",
                    """
CREATE TABLE IF NOT EXISTS catalog_context_contract (
  component_id INT PRIMARY KEY,
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
  component_id INT PRIMARY KEY,
  use_when_json TEXT,
  minimal_wiring_json TEXT,
  required_companions_json TEXT,
  config_keys_json TEXT,
  example_entry TEXT
)
""",
                    """
CREATE TABLE IF NOT EXISTS catalog_param_contract (
  id INT AUTO_INCREMENT PRIMARY KEY,
  component_id INT,
  name VARCHAR(128),
  type TEXT,
  default_value TEXT,
  required TINYINT(1),
  description TEXT,
  source VARCHAR(32),
  order_index INT
)
""",
                    """
CREATE TABLE IF NOT EXISTS catalog_method_contract (
  id INT AUTO_INCREMENT PRIMARY KEY,
  component_id INT,
  name VARCHAR(128),
  required TINYINT(1),
  implemented TINYINT(1),
  signature TEXT,
  origin VARCHAR(32)
)
""",
                    """
CREATE TABLE IF NOT EXISTS catalog_health (
  component_id INT PRIMARY KEY,
  import_ok TINYINT(1),
  context_ok TINYINT(1),
  methods_ok TINYINT(1),
  params_ok TINYINT(1),
  issues_json TEXT,
  last_checked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
)
""",
                ),
            ),
            (
                2,
                (
                    "ALTER TABLE catalog_component ADD COLUMN companions_json TEXT",
                ),
            ),
            (
                3,
                (
                    "ALTER TABLE catalog_component CONVERT TO CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci",
                    "ALTER TABLE catalog_context_contract CONVERT TO CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci",
                    "ALTER TABLE catalog_usage_contract CONVERT TO CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci",
                    "ALTER TABLE catalog_param_contract CONVERT TO CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci",
                    "ALTER TABLE catalog_method_contract CONVERT TO CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci",
                    "ALTER TABLE catalog_health CONVERT TO CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci",
                ),
            ),
            (
                4,
                (
                    f"""
CREATE TABLE IF NOT EXISTS catalog_api_index (
  id INT AUTO_INCREMENT PRIMARY KEY,
  profile VARCHAR(32),
  module_path VARCHAR(191),
  class_name VARCHAR(191),
  method_name VARCHAR(191),
  purpose TEXT,
  `usage` TEXT,
  lineno INT,
  last_sync_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  UNIQUE KEY uniq_api_index (profile, module_path, class_name, method_name)
) CHARACTER SET {_MYSQL_CHARSET} COLLATE {_MYSQL_COLLATION}
""",
                    f"""
CREATE TABLE IF NOT EXISTS catalog_api_index_meta (
  profile VARCHAR(32) PRIMARY KEY,
  file_count INT,
  component_count INT,
  method_count INT,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) CHARACTER SET {_MYSQL_CHARSET} COLLATE {_MYSQL_COLLATION}
""",
                ),
            ),
            (
                5,
                (
                    f"""
CREATE TABLE IF NOT EXISTS catalog_api_doc (
  id INT AUTO_INCREMENT PRIMARY KEY,
  profile VARCHAR(32),
  module_path VARCHAR(191),
  class_name VARCHAR(191),
  method_name VARCHAR(191),
  params_json TEXT,
  boundaries TEXT,
  side_effects TEXT,
  lifecycle TEXT,
  auto_fields_json TEXT,
  notes TEXT,
  last_sync_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  UNIQUE KEY uniq_api_doc (profile, module_path, class_name, method_name)
) CHARACTER SET {_MYSQL_CHARSET} COLLATE {_MYSQL_COLLATION}
""",
                ),
            ),
            (
                6,
                (
                    "ALTER TABLE catalog_api_doc ADD COLUMN auto_fields_json TEXT",
                    "ALTER TABLE catalog_api_doc CONVERT TO CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci",
                ),
            ),
            (
                7,
                (
                    f"""
CREATE TABLE IF NOT EXISTS catalog_field_value (
  id INT AUTO_INCREMENT PRIMARY KEY,
  component_id INT NOT NULL,
  field_scope VARCHAR(32) NOT NULL,
  field_name VARCHAR(128) NOT NULL,
  field_value VARCHAR(512) NOT NULL,
  field_value_norm VARCHAR(512) NOT NULL,
  KEY idx_catalog_field_component (component_id),
  KEY idx_catalog_field_name (field_name),
  KEY idx_catalog_field_name_norm (field_name, field_value_norm)
) CHARACTER SET {_MYSQL_CHARSET} COLLATE {_MYSQL_COLLATION}
""",
                ),
            ),
            (
                8,
                (
                    "ALTER TABLE catalog_context_contract ADD COLUMN artifact_requires_json TEXT",
                    "ALTER TABLE catalog_context_contract ADD COLUMN artifact_provides_json TEXT",
                    "ALTER TABLE catalog_context_contract ADD COLUMN phase_in_json TEXT",
                    "ALTER TABLE catalog_context_contract ADD COLUMN phase_out_json TEXT",
                ),
            ),
        ]

        for version, statements in migrations:
            if version in applied:
                continue
            for stmt in statements:
                safe_exec(stmt)
            cur.execute(
                "INSERT INTO catalog_schema_migrations (version) VALUES (%s)",
                (int(version),),
            )
            conn.commit()
        cur.close()

    def _ensure_field_value_index(self, conn) -> None:
        cur = conn.cursor()
        try:
            cur.execute("SELECT COUNT(*) FROM catalog_field_value")
            row = cur.fetchone()
            field_value_count = int((row.get("COUNT(*)") if isinstance(row, dict) else row[0]) or 0) if row else 0
            if field_value_count > 0:
                return
            cur.execute("SELECT COUNT(*) FROM catalog_component")
            component_row = cur.fetchone()
            component_count = int((component_row.get("COUNT(*)") if isinstance(component_row, dict) else component_row[0]) or 0) if component_row else 0
            if component_count <= 0:
                return
        finally:
            cur.close()

        cur = conn.cursor()
        cur.execute(
            """
SELECT c.id, c.`key`, c.kind, c.title, c.import_path, c.summary, c.tags, c.companions_json,
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
                key = f"{field_scope}|{field_name}|{norm}"
                if key in seen:
                    continue
                seen.add(key)
                insert_rows.append((component_id, field_scope, field_name, value, norm))

        for row in rows:
            if isinstance(row, dict):
                rec = row
            else:
                (
                    component_id,
                    key,
                    kind_value,
                    title,
                    import_path,
                    summary,
                    tags_json,
                    companions_json,
                    req_json,
                    prov_json,
                    mut_json,
                    cache_json,
                    notes_json,
                    artifact_requires_json,
                    artifact_provides_json,
                    phase_in_json,
                    phase_out_json,
                    use_when_json,
                    wiring_json,
                    required_companions_json,
                    config_keys_json,
                    example_entry,
                ) = row
                rec = {
                    "id": component_id,
                    "key": key,
                    "kind": kind_value,
                    "title": title,
                    "import_path": import_path,
                    "summary": summary,
                    "tags": tags_json,
                    "companions": companions_json,
                    "context_requires": req_json,
                    "context_provides": prov_json,
                    "context_mutates": mut_json,
                    "context_cache": cache_json,
                    "context_notes": notes_json,
                    "artifact_requires": artifact_requires_json,
                    "artifact_provides": artifact_provides_json,
                    "phase_in": phase_in_json,
                    "phase_out": phase_out_json,
                    "use_when": use_when_json,
                    "minimal_wiring": wiring_json,
                    "required_companions": required_companions_json,
                    "config_keys": config_keys_json,
                    "example_entry": example_entry,
                }
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
            add_rows(component_id, "base", "companions", self._load_json_tuple(rec.get("companions")))
            add_rows(component_id, "context", "context_requires", self._load_json_tuple(rec.get("context_requires")))
            add_rows(component_id, "context", "context_provides", self._load_json_tuple(rec.get("context_provides")))
            add_rows(component_id, "context", "context_mutates", self._load_json_tuple(rec.get("context_mutates")))
            add_rows(component_id, "context", "context_cache", self._load_json_tuple(rec.get("context_cache")))
            add_rows(component_id, "context", "context_notes", self._load_json_tuple(rec.get("context_notes")))
            add_rows(component_id, "context", "artifact_requires", self._load_json_tuple(rec.get("artifact_requires")))
            add_rows(component_id, "context", "artifact_provides", self._load_json_tuple(rec.get("artifact_provides")))
            add_rows(component_id, "context", "phase_in", self._load_json_tuple(rec.get("phase_in")))
            add_rows(component_id, "context", "phase_out", self._load_json_tuple(rec.get("phase_out")))
            add_rows(component_id, "usage", "use_when", self._load_json_tuple(rec.get("use_when")))
            add_rows(component_id, "usage", "minimal_wiring", self._load_json_tuple(rec.get("minimal_wiring")))
            add_rows(component_id, "usage", "required_companions", self._load_json_tuple(rec.get("required_companions")))
            add_rows(component_id, "usage", "config_keys", self._load_json_tuple(rec.get("config_keys")))
            add_rows(component_id, "usage", "example_entry", rec.get("example_entry"))

        if not insert_rows:
            return
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

    def sync_bundle(self, bundle: CatalogBundle, *, profile: str = "default") -> None:
        if self._readonly:
            raise RuntimeError("Catalog store is read-only (NSGABLACK_CATALOG_DB_READONLY=1).")

        conn = _connect_mysql(self._cfg)
        try:
            self._ensure_schema(conn)
            self._delete_stale_components(
                conn,
                current_keys=tuple(component.key for component in bundle.components),
            )
            component_ids = self._upsert_components(conn, bundle.components)
            self._upsert_contexts(conn, component_ids, bundle.contexts)
            self._upsert_usages(conn, component_ids, bundle.usages)
            self._replace_field_values(conn, component_ids, bundle.components, bundle.contexts, bundle.usages)
            self._replace_params(conn, component_ids, bundle.params)
            self._replace_methods(conn, component_ids, bundle.methods)
            self._upsert_health(conn, component_ids, bundle.health)
            conn.commit()
        finally:
            try:
                conn.close()
            except Exception:
                pass

    def update_health(
        self,
        components: Sequence[CatalogComponentContract],
        health: Sequence[HealthContract],
    ) -> None:
        if self._readonly:
            raise RuntimeError("Catalog store is read-only (NSGABLACK_CATALOG_DB_READONLY=1).")

        conn = _connect_mysql(self._cfg)
        try:
            self._ensure_schema(conn)
            component_ids = self._upsert_components(conn, components)
            self._upsert_health(conn, component_ids, health)
            conn.commit()
        finally:
            try:
                conn.close()
            except Exception:
                pass

    def _upsert_components(
        self,
        conn,
        components: Sequence[CatalogComponentContract],
    ) -> Dict[str, int]:
        cur = conn.cursor()
        for comp in components:
            cur.execute(
                """
INSERT INTO catalog_component
(`key`, kind, title, import_path, summary, tags, companions_json, source_scope, source_hash)
VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
ON DUPLICATE KEY UPDATE
  kind=VALUES(kind),
  title=VALUES(title),
  import_path=VALUES(import_path),
  summary=VALUES(summary),
  tags=VALUES(tags),
  companions_json=VALUES(companions_json),
  source_scope=VALUES(source_scope),
  source_hash=VALUES(source_hash)
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
        conn.commit()

        keys = [c.key for c in components]
        if not keys:
            return {}

        fmt = ", ".join(["%s"] * len(keys))
        cur.execute(f"SELECT id, `key` FROM catalog_component WHERE `key` IN ({fmt})", tuple(keys))
        rows = cur.fetchall() or []
        out: Dict[str, int] = {}
        for row in rows:
            if isinstance(row, dict):
                out[str(row.get("key"))] = int(row.get("id"))
            else:
                out[str(row[1])] = int(row[0])
        cur.close()
        return out

    def _upsert_contexts(
        self,
        conn,
        component_ids: Dict[str, int],
        contexts: Sequence[CatalogContextContract],
    ) -> None:
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
ON DUPLICATE KEY UPDATE
  requires_json=VALUES(requires_json),
  provides_json=VALUES(provides_json),
  mutates_json=VALUES(mutates_json),
  cache_json=VALUES(cache_json),
  notes_json=VALUES(notes_json),
  artifact_requires_json=VALUES(artifact_requires_json),
  artifact_provides_json=VALUES(artifact_provides_json),
  phase_in_json=VALUES(phase_in_json),
  phase_out_json=VALUES(phase_out_json)
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

    def _upsert_usages(
        self,
        conn,
        component_ids: Dict[str, int],
        usages: Sequence[UsageContract],
    ) -> None:
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
ON DUPLICATE KEY UPDATE
  use_when_json=VALUES(use_when_json),
  minimal_wiring_json=VALUES(minimal_wiring_json),
  required_companions_json=VALUES(required_companions_json),
  config_keys_json=VALUES(config_keys_json),
  example_entry=VALUES(example_entry)
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
        contexts: Sequence[CatalogContextContract],
        usages: Sequence[UsageContract],
    ) -> None:
        cur = conn.cursor()
        ids = tuple(component_ids.values())
        if ids:
            fmt = ", ".join(["%s"] * len(ids))
            cur.execute(f"DELETE FROM catalog_field_value WHERE component_id IN ({fmt})", ids)

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
                key = f"{field_scope}|{field_name}|{norm}"
                if key in seen:
                    continue
                seen.add(key)
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
                add_values(component_id, "context", "artifact_requires", context.artifact_requires)
                add_values(component_id, "context", "artifact_provides", context.artifact_provides)
                add_values(component_id, "context", "phase_in", context.phase_in)
                add_values(component_id, "context", "phase_out", context.phase_out)

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

    def _replace_params(
        self,
        conn,
        component_ids: Dict[str, int],
        params: Sequence[ParamContract],
    ) -> None:
        cur = conn.cursor()
        ids = tuple(component_ids.values())
        if ids:
            fmt = ", ".join(["%s"] * len(ids))
            cur.execute(f"DELETE FROM catalog_param_contract WHERE component_id IN ({fmt})", ids)
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
                    int(bool(p.required)),
                    p.desc,
                    p.source,
                    int(p.order_index),
                ),
            )
        cur.close()

    def _replace_methods(
        self,
        conn,
        component_ids: Dict[str, int],
        methods: Sequence[MethodContract],
    ) -> None:
        cur = conn.cursor()
        ids = tuple(component_ids.values())
        if ids:
            fmt = ", ".join(["%s"] * len(ids))
            cur.execute(f"DELETE FROM catalog_method_contract WHERE component_id IN ({fmt})", ids)
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
                    int(bool(m.required)),
                    int(bool(m.implemented)),
                    m.signature,
                    m.origin,
                ),
            )
        cur.close()

    def _upsert_health(
        self,
        conn,
        component_ids: Dict[str, int],
        health: Sequence[HealthContract],
    ) -> None:
        cur = conn.cursor()
        for h in health:
            cid = component_ids.get(h.component_key)
            if cid is None:
                continue
            cur.execute(
                """
INSERT INTO catalog_health
(component_id, import_ok, context_ok, methods_ok, params_ok, issues_json)
VALUES (%s, %s, %s, %s, %s, %s)
ON DUPLICATE KEY UPDATE
  import_ok=VALUES(import_ok),
  context_ok=VALUES(context_ok),
  methods_ok=VALUES(methods_ok),
  params_ok=VALUES(params_ok),
  issues_json=VALUES(issues_json)
""",
                (
                    cid,
                    int(bool(h.import_ok)),
                    int(bool(h.context_ok)),
                    int(bool(h.methods_ok)),
                    int(bool(h.params_ok)),
                    json.dumps(list(h.issues), ensure_ascii=False),
                ),
            )
        cur.close()

    def _delete_stale_components(self, conn, *, current_keys: Sequence[str]) -> None:
        """Replace the source-owned component set instead of accumulating tombstones."""

        keep = {str(key).strip() for key in current_keys if str(key).strip()}
        cur = conn.cursor()
        cur.execute("SELECT id, `key` FROM catalog_component")
        rows = cur.fetchall() or []
        stale_ids: List[int] = []
        for row in rows:
            component_id = int(row.get("id")) if isinstance(row, Mapping) else int(row[0])
            key = str(row.get("key", "") if isinstance(row, Mapping) else row[1]).strip()
            if key not in keep:
                stale_ids.append(component_id)
        if stale_ids:
            placeholders = ", ".join(["%s"] * len(stale_ids))
            params = tuple(stale_ids)
            for table in (
                "catalog_field_value",
                "catalog_param_contract",
                "catalog_method_contract",
                "catalog_health",
                "catalog_context_contract",
                "catalog_usage_contract",
            ):
                cur.execute(
                    f"DELETE FROM {table} WHERE component_id IN ({placeholders})",
                    params,
                )
            cur.execute(
                f"DELETE FROM catalog_component WHERE id IN ({placeholders})",
                params,
            )
        conn.commit()
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
        use_context_in_all = normalized_field == "all" and any(
            ("context" in token)
            or token in {"requires", "provides", "mutates", "cache", "contract", "contracts", "artifact", "artifacts", "phase"}
            for token in tokens
        )
        use_usage_in_all = normalized_field == "all" and any(
            token in {"use", "usage", "wiring", "wire", "companion", "companions", "config", "example"}
            for token in tokens
        )
        for token_group in _expand_token_groups(tokens):
            alias_clauses: List[str] = []
            for alias in token_group:
                pattern = _like_pattern(alias)
                if normalized_field == "name":
                    alias_clauses.append("(LOWER(c.`key`) LIKE %s OR LOWER(c.title) LIKE %s)")
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
                    all_clauses = [
                        "LOWER(c.`key`) LIKE %s",
                        "LOWER(c.title) LIKE %s",
                        "LOWER(c.kind) LIKE %s",
                        "LOWER(c.summary) LIKE %s",
                        "EXISTS (SELECT 1 FROM catalog_field_value fv_search "
                        "WHERE fv_search.component_id = c.id AND fv_search.field_name = 'tags' "
                        "AND fv_search.field_value_norm LIKE %s)",
                    ]
                    params.extend([pattern] * 5)
                    if use_context_in_all:
                        placeholders = ", ".join(["%s"] * len(_CONTEXT_FIELD_NAMES))
                        all_clauses.append(
                            "EXISTS (SELECT 1 FROM catalog_field_value fv_search "
                            "WHERE fv_search.component_id = c.id "
                            f"AND fv_search.field_name IN ({placeholders}) "
                            "AND fv_search.field_value_norm LIKE %s)"
                        )
                        params.extend([*_CONTEXT_FIELD_NAMES, pattern])
                    if use_usage_in_all:
                        placeholders = ", ".join(["%s"] * len(_USAGE_FIELD_NAMES))
                        all_clauses.append(
                            "EXISTS (SELECT 1 FROM catalog_field_value fv_search "
                            "WHERE fv_search.component_id = c.id "
                            f"AND fv_search.field_name IN ({placeholders}) "
                            "AND fv_search.field_value_norm LIKE %s)"
                        )
                        params.extend([*_USAGE_FIELD_NAMES, pattern])
                    alias_clauses.append("(" + " OR ".join(all_clauses) + ")")
            if alias_clauses:
                clauses.append("(" + " OR ".join(alias_clauses) + ")")

        cur = conn.cursor()
        cur.execute(
            """
SELECT c.id, c.`key`, c.kind, c.title, c.import_path, c.summary, c.tags, c.companions_json,
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
        for row in rows:
            if isinstance(row, dict):
                records.append(row)
                continue
            (
                _id,
                key,
                kind_value,
                title,
                import_path,
                summary,
                tags_json,
                companions_json,
                req_json,
                prov_json,
                mut_json,
                cache_json,
                notes_json,
                artifact_requires_json,
                artifact_provides_json,
                phase_in_json,
                phase_out_json,
                use_when_json,
                wiring_json,
                required_companions_json,
                config_keys_json,
                example_entry,
            ) = row
            records.append(
                {
                    "id": _id,
                    "key": key,
                    "kind": kind_value,
                    "title": title,
                    "import_path": import_path,
                    "summary": summary,
                    "tags": tags_json,
                    "companions": companions_json,
                    "context_requires": req_json,
                    "context_provides": prov_json,
                    "context_mutates": mut_json,
                    "context_cache": cache_json,
                    "context_notes": notes_json,
                    "artifact_requires": artifact_requires_json,
                    "artifact_provides": artifact_provides_json,
                    "phase_in": phase_in_json,
                    "phase_out": phase_out_json,
                    "use_when": use_when_json,
                    "minimal_wiring": wiring_json,
                    "required_companions": required_companions_json,
                    "config_keys": config_keys_json,
                    "example_entry": example_entry,
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
        conn = _connect_mysql(self._cfg)
        try:
            self._ensure_schema(conn)
            entries = self._catalog_entries_from_query(
                conn,
                profile=profile,
                kind=kind,
                tags=tags,
                field_filters=field_filters,
            )
            if limit is None:
                return entries
            return entries[: max(0, int(limit))]
        finally:
            try:
                conn.close()
            except Exception:
                pass

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
        conn = _connect_mysql(self._cfg)
        try:
            self._ensure_schema(conn)
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
            try:
                conn.close()
            except Exception:
                pass

    def get_catalog_entry(self, key: str, *, profile: str = "default") -> Optional[CatalogEntry]:
        normalized_key = str(key or "").strip()
        if not normalized_key:
            return None
        conn = _connect_mysql(self._cfg)
        try:
            self._ensure_schema(conn)
            records = self._catalog_row_records(
                conn,
                profile=profile,
                field_filters={"key": (normalized_key,)},
            )
            for rec in records:
                if str(rec.get("key", "") or "").strip() != normalized_key:
                    continue
                return self._catalog_entry_from_record(rec, profile=profile)
            return None
        finally:
            try:
                conn.close()
            except Exception:
                pass

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
        conn = _connect_mysql(self._cfg)
        try:
            self._ensure_schema(conn)
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
                values: Tuple[str, ...]
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
            try:
                conn.close()
            except Exception:
                pass

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
        companions = [
            {
                "key": item.key,
                "title": item.title,
                "kind": item.kind,
                "summary": item.summary,
            }
            for item in companion_entries
        ]
        missing_companions = tuple(companion_key for companion_key in entry.companions if companion_key not in companions_by_key)
        linked_by_entries = [item for item in all_entries if entry.key in tuple(item.companions or ())]
        linked_by = [
            {
                "key": item.key,
                "title": item.title,
                "kind": item.kind,
                "summary": item.summary,
            }
            for item in linked_by_entries
            if item.key != entry.key
        ]
        contract_sections = build_contract_neighbor_sections(entry, candidates=all_entries)
        return {
            "key": entry.key,
            "companions": companions,
            "missing_companions": missing_companions,
            "linked_by": linked_by,
            **contract_sections,
        }

    def load_entries(self) -> List[Dict[str, object]]:
        entries = self.list_catalog_entries(profile="default", limit=None)
        return [
            {
                "key": entry.key,
                "kind": entry.kind,
                "title": entry.title,
                "import_path": entry.import_path,
                "summary": entry.summary,
                "tags": tuple(entry.tags),
                "companions": tuple(entry.companions),
                "context_requires": tuple(entry.context_requires),
                "context_provides": tuple(entry.context_provides),
                "context_mutates": tuple(entry.context_mutates),
                "context_cache": tuple(entry.context_cache),
                "context_notes": tuple(entry.context_notes),
                "artifact_requires": tuple(getattr(entry, "artifact_requires", ()) or ()),
                "artifact_provides": tuple(getattr(entry, "artifact_provides", ()) or ()),
                "phase_in": tuple(getattr(entry, "phase_in", ()) or ()),
                "phase_out": tuple(getattr(entry, "phase_out", ()) or ()),
                "use_when": tuple(entry.use_when),
                "minimal_wiring": tuple(entry.minimal_wiring),
                "required_companions": tuple(entry.required_companions),
                "config_keys": tuple(entry.config_keys),
                "example_entry": str(entry.example_entry or ""),
            }
            for entry in entries
        ]

    def sync_api_index(
        self,
        entries: Sequence[ApiIndexEntry],
        meta: Optional[ApiIndexMeta],
        *,
        profile: str,
        wipe: bool = True,
    ) -> None:
        if self._readonly:
            raise RuntimeError("Catalog store is read-only (NSGABLACK_CATALOG_DB_READONLY=1).")

        conn = _connect_mysql(self._cfg)
        try:
            self._ensure_schema(conn)
            cur = conn.cursor()
            prof = str(profile or "").strip().lower() or "default"
            if wipe:
                cur.execute("DELETE FROM catalog_api_index WHERE profile=%s", (prof,))
            if entries:
                cur.executemany(
                    """
INSERT INTO catalog_api_index
  (profile, module_path, class_name, method_name, purpose, `usage`, lineno)
VALUES (%s, %s, %s, %s, %s, %s, %s)
ON DUPLICATE KEY UPDATE
  purpose=VALUES(purpose),
  `usage`=VALUES(`usage`),
  lineno=VALUES(lineno)
""",
                    [
                        (
                            prof,
                            e.module,
                            e.class_name,
                            e.method_name,
                            e.purpose,
                            e.usage,
                            int(e.lineno),
                        )
                        for e in entries
                    ],
                )
            if meta is not None:
                cur.execute(
                    """
INSERT INTO catalog_api_index_meta
  (profile, file_count, component_count, method_count)
VALUES (%s, %s, %s, %s)
ON DUPLICATE KEY UPDATE
  file_count=VALUES(file_count),
  component_count=VALUES(component_count),
  method_count=VALUES(method_count)
""",
                    (
                        prof,
                        int(meta.file_count),
                        int(meta.component_count),
                        int(meta.method_count),
                    ),
                )
            conn.commit()
            cur.close()
        finally:
            try:
                conn.close()
            except Exception:
                pass

    def load_api_index(self, *, profile: str) -> List[ApiIndexEntry]:
        conn = _connect_mysql(self._cfg)
        try:
            self._ensure_schema(conn)
            cur = conn.cursor()
            prof = str(profile or "").strip().lower() or "default"
            cur.execute(
                """
SELECT profile, module_path, class_name, method_name, purpose, `usage`, lineno
FROM catalog_api_index
WHERE profile=%s
""",
                (prof,),
            )
            rows = cur.fetchall() or []
            out: List[ApiIndexEntry] = []
            for row in rows:
                if isinstance(row, dict):
                    rec = row
                    out.append(
                        ApiIndexEntry(
                            profile=str(rec.get("profile", "") or "").strip(),
                            module=str(rec.get("module_path", "") or "").strip(),
                            class_name=str(rec.get("class_name", "") or "").strip(),
                            method_name=str(rec.get("method_name", "") or "").strip(),
                            purpose=str(rec.get("purpose", "") or "").strip(),
                            usage=str(rec.get("usage", "") or "").strip(),
                            lineno=int(rec.get("lineno", 0) or 0),
                        )
                    )
                else:
                    (profile_val, module_path, class_name, method_name, purpose, usage, lineno) = row
                    out.append(
                        ApiIndexEntry(
                            profile=str(profile_val or "").strip(),
                            module=str(module_path or "").strip(),
                            class_name=str(class_name or "").strip(),
                            method_name=str(method_name or "").strip(),
                            purpose=str(purpose or "").strip(),
                            usage=str(usage or "").strip(),
                            lineno=int(lineno or 0),
                        )
                    )
            cur.close()
            return [e for e in out if e.module and e.method_name]
        finally:
            try:
                conn.close()
            except Exception:
                pass

    def load_api_index_meta(self, *, profile: str) -> Optional[ApiIndexMeta]:
        conn = _connect_mysql(self._cfg)
        try:
            self._ensure_schema(conn)
            cur = conn.cursor()
            prof = str(profile or "").strip().lower() or "default"
            cur.execute(
                """
SELECT profile, file_count, component_count, method_count
FROM catalog_api_index_meta
WHERE profile=%s
""",
                (prof,),
            )
            row = cur.fetchone()
            cur.close()
            if not row:
                return None
            if isinstance(row, dict):
                rec = row
                return ApiIndexMeta(
                    profile=str(rec.get("profile", "") or "").strip(),
                    file_count=int(rec.get("file_count", 0) or 0),
                    component_count=int(rec.get("component_count", 0) or 0),
                    method_count=int(rec.get("method_count", 0) or 0),
                )
            profile_val, file_count, component_count, method_count = row
            return ApiIndexMeta(
                profile=str(profile_val or "").strip(),
                file_count=int(file_count or 0),
                component_count=int(component_count or 0),
                method_count=int(method_count or 0),
            )
        finally:
            try:
                conn.close()
            except Exception:
                pass

    def search_api_index(
        self,
        *,
        profile: str,
        query: str,
        field: str = "all",
        limit: int = 20,
    ) -> List[ApiIndexEntry]:
        q = str(query or "").strip()
        if not q:
            return []
        conn = _connect_mysql(self._cfg)
        try:
            self._ensure_schema(conn)
            cur = conn.cursor()
            prof = str(profile or "").strip().lower() or "default"
            field = str(field or "all").strip().lower()
            limit = max(1, int(limit))
            like = f"%{q}%"

            if field == "module":
                where = "module_path LIKE %s"
                params = (prof, like)
            elif field == "class":
                where = "class_name LIKE %s"
                params = (prof, like)
            elif field == "method":
                where = "method_name LIKE %s"
                params = (prof, like)
            elif field == "purpose":
                where = "purpose LIKE %s"
                params = (prof, like)
            elif field == "usage":
                where = "`usage` LIKE %s"
                params = (prof, like)
            else:
                where = "(module_path LIKE %s OR class_name LIKE %s OR method_name LIKE %s OR purpose LIKE %s OR `usage` LIKE %s)"
                params = (prof, like, like, like, like, like)

            cur.execute(
                f"""
SELECT profile, module_path, class_name, method_name, purpose, `usage`, lineno
FROM catalog_api_index
WHERE profile=%s AND {where}
ORDER BY module_path, class_name, lineno, method_name
LIMIT %s
""",
                (*params, limit),
            )
            rows = cur.fetchall() or []
            out: List[ApiIndexEntry] = []
            for row in rows:
                if isinstance(row, dict):
                    rec = row
                    out.append(
                        ApiIndexEntry(
                            profile=str(rec.get("profile", "") or "").strip(),
                            module=str(rec.get("module_path", "") or "").strip(),
                            class_name=str(rec.get("class_name", "") or "").strip(),
                            method_name=str(rec.get("method_name", "") or "").strip(),
                            purpose=str(rec.get("purpose", "") or "").strip(),
                            usage=str(rec.get("usage", "") or "").strip(),
                            lineno=int(rec.get("lineno", 0) or 0),
                        )
                    )
                else:
                    (profile_val, module_path, class_name, method_name, purpose, usage, lineno) = row
                    out.append(
                        ApiIndexEntry(
                            profile=str(profile_val or "").strip(),
                            module=str(module_path or "").strip(),
                            class_name=str(class_name or "").strip(),
                            method_name=str(method_name or "").strip(),
                            purpose=str(purpose or "").strip(),
                            usage=str(usage or "").strip(),
                            lineno=int(lineno or 0),
                        )
                    )
            cur.close()
            return out
        finally:
            try:
                conn.close()
            except Exception:
                pass

    def get_api_index_entry(
        self,
        *,
        profile: str,
        module: str,
        class_name: str,
        method_name: str,
    ) -> Optional[ApiIndexEntry]:
        conn = _connect_mysql(self._cfg)
        try:
            self._ensure_schema(conn)
            cur = conn.cursor()
            prof = str(profile or "").strip().lower() or "default"
            cur.execute(
                """
SELECT profile, module_path, class_name, method_name, purpose, `usage`, lineno
FROM catalog_api_index
WHERE profile=%s AND module_path=%s AND class_name=%s AND method_name=%s
LIMIT 1
""",
                (
                    prof,
                    str(module or "").strip(),
                    str(class_name or "").strip(),
                    str(method_name or "").strip(),
                ),
            )
            row = cur.fetchone()
            cur.close()
            if not row:
                return None
            if isinstance(row, dict):
                rec = row
                return ApiIndexEntry(
                    profile=str(rec.get("profile", "") or "").strip(),
                    module=str(rec.get("module_path", "") or "").strip(),
                    class_name=str(rec.get("class_name", "") or "").strip(),
                    method_name=str(rec.get("method_name", "") or "").strip(),
                    purpose=str(rec.get("purpose", "") or "").strip(),
                    usage=str(rec.get("usage", "") or "").strip(),
                    lineno=int(rec.get("lineno", 0) or 0),
                )
            profile_val, module_path, class_name, method_name, purpose, usage, lineno = row
            return ApiIndexEntry(
                profile=str(profile_val or "").strip(),
                module=str(module_path or "").strip(),
                class_name=str(class_name or "").strip(),
                method_name=str(method_name or "").strip(),
                purpose=str(purpose or "").strip(),
                usage=str(usage or "").strip(),
                lineno=int(lineno or 0),
            )
        finally:
            try:
                conn.close()
            except Exception:
                pass

    def upsert_api_docs(
        self,
        entries: Sequence[ApiDocEntry],
        *,
        profile: str,
    ) -> None:
        if self._readonly:
            raise RuntimeError("Catalog store is read-only (NSGABLACK_CATALOG_DB_READONLY=1).")
        if not entries:
            return
        conn = _connect_mysql(self._cfg)
        try:
            self._ensure_schema(conn)
            cur = conn.cursor()
            prof = str(profile or "").strip().lower() or "default"
            cur.executemany(
                """
INSERT INTO catalog_api_doc
  (profile, module_path, class_name, method_name, params_json, boundaries, side_effects, lifecycle, auto_fields_json, notes)
VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
ON DUPLICATE KEY UPDATE
  params_json=VALUES(params_json),
  boundaries=VALUES(boundaries),
  side_effects=VALUES(side_effects),
  lifecycle=VALUES(lifecycle),
  auto_fields_json=VALUES(auto_fields_json),
  notes=VALUES(notes)
""",
                [
                    (
                        prof,
                        e.module,
                        e.class_name,
                        e.method_name,
                        e.params_json,
                        e.boundaries,
                        e.side_effects,
                        e.lifecycle,
                        json.dumps(list(e.auto_fields), ensure_ascii=False),
                        e.notes,
                    )
                    for e in entries
                ],
            )
            conn.commit()
            cur.close()
        finally:
            try:
                conn.close()
            except Exception:
                pass

    def get_api_doc_entry(
        self,
        *,
        profile: str,
        module: str,
        class_name: str,
        method_name: str,
    ) -> Optional[ApiDocEntry]:
        conn = _connect_mysql(self._cfg)
        try:
            self._ensure_schema(conn)
            cur = conn.cursor()
            prof = str(profile or "").strip().lower() or "default"
            cur.execute(
                """
SELECT profile, module_path, class_name, method_name, params_json, boundaries, side_effects, lifecycle, auto_fields_json, notes
FROM catalog_api_doc
WHERE profile=%s AND module_path=%s AND class_name=%s AND method_name=%s
LIMIT 1
""",
                (
                    prof,
                    str(module or "").strip(),
                    str(class_name or "").strip(),
                    str(method_name or "").strip(),
                ),
            )
            row = cur.fetchone()
            cur.close()
            if not row:
                return None
            if isinstance(row, dict):
                rec = row
                try:
                    auto_fields = tuple(json.loads(rec.get("auto_fields_json") or "[]") or ())
                except Exception:
                    auto_fields = ()
                return ApiDocEntry(
                    profile=str(rec.get("profile", "") or "").strip(),
                    module=str(rec.get("module_path", "") or "").strip(),
                    class_name=str(rec.get("class_name", "") or "").strip(),
                    method_name=str(rec.get("method_name", "") or "").strip(),
                    params_json=str(rec.get("params_json", "") or "").strip(),
                    boundaries=str(rec.get("boundaries", "") or "").strip(),
                    side_effects=str(rec.get("side_effects", "") or "").strip(),
                    lifecycle=str(rec.get("lifecycle", "") or "").strip(),
                    notes=str(rec.get("notes", "") or "").strip(),
                    auto_fields=auto_fields,
                )
            (
                profile_val,
                module_path,
                class_name_val,
                method_name_val,
                params_json,
                boundaries,
                side_effects,
                lifecycle,
                auto_fields_json,
                notes,
            ) = row
            try:
                auto_fields = tuple(json.loads(auto_fields_json or "[]") or ())
            except Exception:
                auto_fields = ()
            return ApiDocEntry(
                profile=str(profile_val or "").strip(),
                module=str(module_path or "").strip(),
                class_name=str(class_name_val or "").strip(),
                method_name=str(method_name_val or "").strip(),
                params_json=str(params_json or "").strip(),
                boundaries=str(boundaries or "").strip(),
                side_effects=str(side_effects or "").strip(),
                lifecycle=str(lifecycle or "").strip(),
                notes=str(notes or "").strip(),
                auto_fields=auto_fields,
            )
        finally:
            try:
                conn.close()
            except Exception:
                pass

    def load_api_doc_entries(self, *, profile: str) -> List[ApiDocEntry]:
        conn = _connect_mysql(self._cfg)
        try:
            self._ensure_schema(conn)
            cur = conn.cursor()
            prof = str(profile or "").strip().lower() or "default"
            cur.execute(
                """
SELECT profile, module_path, class_name, method_name, params_json, boundaries, side_effects, lifecycle, auto_fields_json, notes
FROM catalog_api_doc
WHERE profile=%s
""",
                (prof,),
            )
            rows = cur.fetchall() or []
            out: List[ApiDocEntry] = []
            for row in rows:
                if isinstance(row, dict):
                    rec = row
                    try:
                        auto_fields = tuple(json.loads(rec.get("auto_fields_json") or "[]") or ())
                    except Exception:
                        auto_fields = ()
                    out.append(
                        ApiDocEntry(
                            profile=str(rec.get("profile", "") or "").strip(),
                            module=str(rec.get("module_path", "") or "").strip(),
                            class_name=str(rec.get("class_name", "") or "").strip(),
                            method_name=str(rec.get("method_name", "") or "").strip(),
                            params_json=str(rec.get("params_json", "") or "").strip(),
                            boundaries=str(rec.get("boundaries", "") or "").strip(),
                            side_effects=str(rec.get("side_effects", "") or "").strip(),
                            lifecycle=str(rec.get("lifecycle", "") or "").strip(),
                            notes=str(rec.get("notes", "") or "").strip(),
                            auto_fields=auto_fields,
                        )
                    )
                else:
                    (
                        profile_val,
                        module_path,
                        class_name_val,
                        method_name_val,
                        params_json,
                        boundaries,
                        side_effects,
                        lifecycle,
                        auto_fields_json,
                        notes,
                    ) = row
                    try:
                        auto_fields = tuple(json.loads(auto_fields_json or "[]") or ())
                    except Exception:
                        auto_fields = ()
                    out.append(
                        ApiDocEntry(
                            profile=str(profile_val or "").strip(),
                            module=str(module_path or "").strip(),
                            class_name=str(class_name_val or "").strip(),
                            method_name=str(method_name_val or "").strip(),
                            params_json=str(params_json or "").strip(),
                            boundaries=str(boundaries or "").strip(),
                            side_effects=str(side_effects or "").strip(),
                            lifecycle=str(lifecycle or "").strip(),
                            notes=str(notes or "").strip(),
                            auto_fields=auto_fields,
                        )
                    )
            cur.close()
            return [e for e in out if e.module and e.method_name]
        finally:
            try:
                conn.close()
            except Exception:
                pass

    def list_api_doc_gaps(
        self,
        *,
        profile: str,
        limit: int = 200,
    ) -> List[ApiDocGap]:
        conn = _connect_mysql(self._cfg)
        try:
            self._ensure_schema(conn)
            cur = conn.cursor()
            prof = str(profile or "").strip().lower() or "default"
            limit = max(1, int(limit))
            cur.execute(
                """
SELECT idx.module_path, idx.class_name, idx.method_name,
       doc.params_json, doc.boundaries, doc.side_effects, doc.lifecycle
FROM catalog_api_index AS idx
LEFT JOIN catalog_api_doc AS doc
  ON idx.profile = doc.profile
 AND idx.module_path = doc.module_path
 AND idx.class_name = doc.class_name
 AND idx.method_name = doc.method_name
WHERE idx.profile=%s AND (
  doc.module_path IS NULL
  OR doc.params_json IS NULL OR doc.params_json = ''
  OR doc.boundaries IS NULL OR doc.boundaries = ''
  OR doc.side_effects IS NULL OR doc.side_effects = ''
  OR doc.lifecycle IS NULL OR doc.lifecycle = ''
)
ORDER BY idx.module_path, idx.class_name, idx.method_name
LIMIT %s
""",
                (prof, limit),
            )
            rows = cur.fetchall() or []
            gaps: List[ApiDocGap] = []
            for row in rows:
                if isinstance(row, dict):
                    module_path = row.get("module_path")
                    class_name = row.get("class_name")
                    method_name = row.get("method_name")
                    params_json = row.get("params_json")
                    boundaries = row.get("boundaries")
                    side_effects = row.get("side_effects")
                    lifecycle = row.get("lifecycle")
                else:
                    module_path, class_name, method_name, params_json, boundaries, side_effects, lifecycle = row
                missing: List[str] = []
                if not params_json:
                    missing.append("params")
                if not boundaries:
                    missing.append("boundaries")
                if not side_effects:
                    missing.append("side_effects")
                if not lifecycle:
                    missing.append("lifecycle")
                gaps.append(
                    ApiDocGap(
                        profile=prof,
                        module=str(module_path or "").strip(),
                        class_name=str(class_name or "").strip(),
                        method_name=str(method_name or "").strip(),
                        missing_fields=tuple(missing),
                    )
                )
            cur.close()
            return gaps
        finally:
            try:
                conn.close()
            except Exception:
                pass
