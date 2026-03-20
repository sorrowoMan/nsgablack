from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Sequence, Tuple
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
    ContextContract,
    HealthContract,
    MethodContract,
    ParamContract,
    UsageContract,
)


_MYSQL_CHARSET = "utf8mb4"
_MYSQL_COLLATION = "utf8mb4_unicode_ci"


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
    if env_url:
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
    if env_url:
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
        try:
            conn = mysql_connector.connect(
                host=cfg.host,
                port=int(cfg.port),
                user=cfg.user,
                password=cfg.password,
                database=cfg.database,
                connection_timeout=int(cfg.connect_timeout),
                charset=_MYSQL_CHARSET,
                collation=_MYSQL_COLLATION,
                use_unicode=True,
            )
        except TypeError:
            conn = mysql_connector.connect(
                host=cfg.host,
                port=int(cfg.port),
                user=cfg.user,
                password=cfg.password,
                database=cfg.database,
                connection_timeout=int(cfg.connect_timeout),
                charset=_MYSQL_CHARSET,
                use_unicode=True,
            )
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
  notes_json TEXT
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

    def sync_bundle(self, bundle: CatalogBundle) -> None:
        if self._readonly:
            raise RuntimeError("Catalog store is read-only (NSGABLACK_CATALOG_DB_READONLY=1).")

        conn = _connect_mysql(self._cfg)
        try:
            self._ensure_schema(conn)
            component_ids = self._upsert_components(conn, bundle.components)
            self._upsert_contexts(conn, component_ids, bundle.contexts)
            self._upsert_usages(conn, component_ids, bundle.usages)
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
        contexts: Sequence[ContextContract],
    ) -> None:
        cur = conn.cursor()
        for ctx in contexts:
            cid = component_ids.get(ctx.component_key)
            if cid is None:
                continue
            cur.execute(
                """
INSERT INTO catalog_context_contract
(component_id, requires_json, provides_json, mutates_json, cache_json, notes_json)
VALUES (%s, %s, %s, %s, %s, %s)
ON DUPLICATE KEY UPDATE
  requires_json=VALUES(requires_json),
  provides_json=VALUES(provides_json),
  mutates_json=VALUES(mutates_json),
  cache_json=VALUES(cache_json),
  notes_json=VALUES(notes_json)
""",
                (
                    cid,
                    json.dumps(list(ctx.requires), ensure_ascii=False),
                    json.dumps(list(ctx.provides), ensure_ascii=False),
                    json.dumps(list(ctx.mutates), ensure_ascii=False),
                    json.dumps(list(ctx.cache), ensure_ascii=False),
                    json.dumps(list(ctx.notes), ensure_ascii=False),
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

    def load_entries(self) -> List[Dict[str, object]]:
        conn = _connect_mysql(self._cfg)
        try:
            self._ensure_schema(conn)
            cur = conn.cursor()
            cur.execute(
                """
SELECT c.id, c.`key`, c.kind, c.title, c.import_path, c.summary, c.tags, c.companions_json,
       ctx.requires_json, ctx.provides_json, ctx.mutates_json, ctx.cache_json, ctx.notes_json,
       usage_tbl.use_when_json, usage_tbl.minimal_wiring_json, usage_tbl.required_companions_json,
       usage_tbl.config_keys_json, usage_tbl.example_entry
FROM catalog_component AS c
LEFT JOIN catalog_context_contract AS ctx ON c.id = ctx.component_id
LEFT JOIN catalog_usage_contract AS usage_tbl ON c.id = usage_tbl.component_id
"""
            )
            rows = cur.fetchall() or []
            out: List[Dict[str, object]] = []
            for row in rows:
                if isinstance(row, dict):
                    rec = row
                else:
                    (
                        _id,
                        key,
                        kind,
                        title,
                        import_path,
                        summary,
                        tags_json,
                        component_companions_json,
                        req_json,
                        prov_json,
                        mut_json,
                        cache_json,
                        notes_json,
                        use_when_json,
                        wiring_json,
                        required_companions_json,
                        config_keys_json,
                        example_entry,
                    ) = row
                    rec = {
                        "key": key,
                        "kind": kind,
                        "title": title,
                        "import_path": import_path,
                        "summary": summary,
                        "tags": tags_json,
                        "companions": component_companions_json,
                        "context_requires": req_json,
                        "context_provides": prov_json,
                        "context_mutates": mut_json,
                        "context_cache": cache_json,
                        "context_notes": notes_json,
                        "use_when": use_when_json,
                        "minimal_wiring": wiring_json,
                        "required_companions": required_companions_json,
                        "config_keys": config_keys_json,
                        "example_entry": example_entry,
                    }

                def _load_json(val: object) -> Tuple[str, ...]:
                    if not val:
                        return ()
                    if isinstance(val, (list, tuple)):
                        return tuple(str(v) for v in val)
                    if isinstance(val, str):
                        try:
                            parsed = json.loads(val)
                            if isinstance(parsed, list):
                                return tuple(str(v) for v in parsed)
                        except Exception:
                            pass
                        return (val,)
                    return ()

                out.append(
                    {
                        "key": str(rec.get("key", "")).strip(),
                        "kind": str(rec.get("kind", "")).strip(),
                        "title": str(rec.get("title", "")).strip(),
                        "import_path": str(rec.get("import_path", "")).strip(),
                        "summary": str(rec.get("summary", "") or "").strip(),
                        "tags": _load_json(rec.get("tags")),
                        "context_requires": _load_json(rec.get("context_requires")),
                        "context_provides": _load_json(rec.get("context_provides")),
                        "context_mutates": _load_json(rec.get("context_mutates")),
                        "context_cache": _load_json(rec.get("context_cache")),
                        "context_notes": _load_json(rec.get("context_notes")),
                        "use_when": _load_json(rec.get("use_when")),
                        "minimal_wiring": _load_json(rec.get("minimal_wiring")),
                        "required_companions": _load_json(rec.get("required_companions")),
                        "config_keys": _load_json(rec.get("config_keys")),
                        "example_entry": str(rec.get("example_entry", "") or "").strip(),
                    }
                )
            cur.close()
            return [e for e in out if e.get("key") and e.get("kind") and e.get("import_path")]
        finally:
            try:
                conn.close()
            except Exception:
                pass

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
