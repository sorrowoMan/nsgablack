from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
import sqlite3
from typing import Any, Mapping, Sequence
from urllib.parse import quote_plus, urlparse

try:
    import tomllib as _toml
except Exception:  # pragma: no cover
    try:
        import tomli as _toml  # type: ignore[import-not-found]
    except Exception:  # pragma: no cover
        _toml = None

try:
    from psycopg import connect as _pg_connect
    from psycopg.rows import dict_row as _pg_dict_row
except Exception:  # pragma: no cover
    _pg_connect = None
    _pg_dict_row = None


_DEFAULT_SQLITE_TARGET = "runs/runtime_surface.sqlite3"
_POSTGRES_SCHEMES = {"postgres", "postgresql", "postgresql+psycopg", "postgresql+psycopg2"}
_SQLITE_SCHEMES = {"sqlite", "sqlite3", "sqlite+pysqlite"}


def _truthy_env(name: str) -> bool:
    return str(os.environ.get(name, "") or "").strip().lower() in {"1", "true", "yes", "on"}


def _normalize_mode(value: str | None) -> str:
    key = str(value or "").strip().lower()
    if key in {"only", "prefer", "off"}:
        return key
    if key == "disabled":
        return "off"
    return "prefer"


def _url_scheme(raw: str | None) -> str:
    text = str(raw or "").strip()
    if not text:
        return ""
    try:
        return str(urlparse(text).scheme or "").strip().lower()
    except Exception:
        return ""


def _is_postgres_target(raw: str | None) -> bool:
    return _url_scheme(raw) in _POSTGRES_SCHEMES


def _is_sqlite_url(raw: str | None) -> bool:
    return _url_scheme(raw) in _SQLITE_SCHEMES


def _safe_target_label(target: str) -> str:
    text = str(target or "").strip()
    if not text:
        return text
    if not _is_postgres_target(text):
        return text
    parsed = urlparse(text)
    host = parsed.hostname or "localhost"
    port = f":{parsed.port}" if parsed.port else ""
    user = quote_plus(parsed.username or "postgres")
    auth = f"{user}:***@" if parsed.username else ""
    path = parsed.path or ""
    return f"{parsed.scheme}://{auth}{host}{port}{path}"


def _read_toml_file(path: Path) -> dict[str, Any]:
    if _toml is None or not path.exists() or not path.is_file():
        return {}
    try:
        payload = _toml.loads(path.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return {}
    return dict(payload) if isinstance(payload, dict) else {}


def _read_experiment_db_config_file() -> tuple[dict[str, Any], str | None]:
    env_path = str(os.environ.get("NSGABLACK_EXPERIMENT_DB_CONFIG", "") or "").strip()
    candidates: list[Path] = []
    if env_path:
        candidates.append(Path(env_path))
    candidates.append(Path.cwd() / "experiment" / "db.toml")
    candidates.append(Path(__file__).resolve().parent / "db.toml")
    for path in candidates:
        payload = _read_toml_file(path)
        if payload:
            return payload, str(path.resolve())
    return {}, None


def _read_catalog_db_config_file() -> tuple[dict[str, Any], str | None]:
    candidates = [Path.cwd() / "catalog" / "db.toml", Path(__file__).resolve().parents[1] / "catalog" / "db.toml"]
    for path in candidates:
        payload = _read_toml_file(path)
        if payload:
            return payload, str(path.resolve())
    return {}, None


def _postgres_block(payload: Mapping[str, Any]) -> dict[str, Any]:
    for key in ("postgres", "postgresql"):
        block = payload.get(key)
        if isinstance(block, dict):
            return dict(block)
    return {}


def _sqlite_block(payload: Mapping[str, Any]) -> dict[str, Any]:
    for key in ("sqlite", "sqlite3"):
        block = payload.get(key)
        if isinstance(block, dict):
            return dict(block)
    return {}


def _target_from_sqlite_block(block: Mapping[str, Any]) -> str | None:
    raw = str(block.get("path", block.get("db_path", block.get("database", ""))) or "").strip()
    return raw or None


def _target_from_postgres_block(block: Mapping[str, Any]) -> str | None:
    raw_url = str(block.get("url", block.get("db_url", "")) or "").strip()
    if raw_url:
        return raw_url
    if not block:
        return None
    host = str(block.get("host", "127.0.0.1") or "127.0.0.1").strip() or "127.0.0.1"
    port = int(block.get("port", 5432))
    user = str(block.get("user", "postgres") or "postgres").strip() or "postgres"
    password = str(block.get("password", "") or "").strip()
    database = str(block.get("database", "postgres") or "postgres").strip() or "postgres"
    connect_timeout = int(block.get("connect_timeout", 10))
    auth = quote_plus(user)
    if password:
        auth += f":{quote_plus(password)}"
    return f"postgresql://{auth}@{host}:{port}/{database}?connect_timeout={connect_timeout}"


@dataclass(frozen=True)
class ExperimentDbResolvedConfig:
    target: str
    source: str
    config_path: str | None
    mode: str
    readonly: bool


def experiment_db_resolved_config() -> ExperimentDbResolvedConfig | None:
    env_target = str(os.environ.get("NSGABLACK_EXPERIMENT_DB_URL", "") or "").strip()
    if env_target:
        return ExperimentDbResolvedConfig(
            target=env_target,
            source="env",
            config_path=None,
            mode=_normalize_mode(os.environ.get("NSGABLACK_EXPERIMENT_DB_MODE")),
            readonly=_truthy_env("NSGABLACK_EXPERIMENT_DB_READONLY"),
        )

    payload, config_path = _read_experiment_db_config_file()
    pg_block = _postgres_block(payload)
    sqlite_block = _sqlite_block(payload)

    pg_enabled = bool(pg_block.get("enabled", False))
    sqlite_enabled = bool(sqlite_block.get("enabled", False))
    mode = _normalize_mode(
        os.environ.get("NSGABLACK_EXPERIMENT_DB_MODE")
        or pg_block.get("mode")
        or sqlite_block.get("mode")
    )

    if pg_enabled:
        target = _target_from_postgres_block(pg_block)
        if target:
            return ExperimentDbResolvedConfig(
                target=target,
                source="file",
                config_path=config_path,
                mode=mode,
                readonly=bool(pg_block.get("readonly", False)) or _truthy_env("NSGABLACK_EXPERIMENT_DB_READONLY"),
            )

    if sqlite_enabled:
        target = _target_from_sqlite_block(sqlite_block)
        if target:
            return ExperimentDbResolvedConfig(
                target=target,
                source="file",
                config_path=config_path,
                mode=mode,
                readonly=bool(sqlite_block.get("readonly", False)) or _truthy_env("NSGABLACK_EXPERIMENT_DB_READONLY"),
            )

    catalog_payload, catalog_path = _read_catalog_db_config_file()
    catalog_pg_block = _postgres_block(catalog_payload)
    if bool(catalog_pg_block.get("enabled", False)):
        target = _target_from_postgres_block(catalog_pg_block)
        if target:
            return ExperimentDbResolvedConfig(
                target=target,
                source="catalog_fallback",
                config_path=catalog_path,
                mode=mode,
                readonly=bool(catalog_pg_block.get("readonly", False)) or _truthy_env("NSGABLACK_EXPERIMENT_DB_READONLY"),
            )

    return None


def resolve_experiment_db_target(explicit_target: str | None = None) -> str:
    explicit = str(explicit_target or "").strip()
    if explicit:
        return explicit
    resolved = experiment_db_resolved_config()
    if resolved is not None:
        return resolved.target
    return _DEFAULT_SQLITE_TARGET


def experiment_db_candidate_targets(explicit_target: str | None = None) -> tuple[str, ...]:
    resolved = experiment_db_resolved_config()
    explicit = str(explicit_target or "").strip()
    resolved_target = str(resolved.target or "").strip() if resolved is not None else ""
    resolved_mode = str(resolved.mode or "").strip().lower() if resolved is not None else ""
    if explicit and (not resolved_target or explicit != resolved_target or resolved_mode == "only"):
        return (explicit,)

    seen: set[str] = set()
    targets: list[str] = []

    def _push(value: str | None) -> None:
        text = str(value or "").strip()
        if not text or text in seen:
            return
        seen.add(text)
        targets.append(text)

    if resolved is not None:
        _push(resolved.target)
        if str(resolved.mode).strip().lower() == "only":
            return tuple(targets)

    payload, _ = _read_experiment_db_config_file()
    sqlite_block = _sqlite_block(payload)
    if bool(sqlite_block.get("enabled", False)):
        _push(_target_from_sqlite_block(sqlite_block))

    default_sqlite_path = Path(_DEFAULT_SQLITE_TARGET).expanduser().resolve()
    if default_sqlite_path.exists() and default_sqlite_path.is_file():
        _push(str(default_sqlite_path))

    if not targets:
        _push(resolve_experiment_db_target())
    return tuple(targets)


def experiment_db_config_info() -> dict[str, Any]:
    resolved = experiment_db_resolved_config()
    target = resolve_experiment_db_target()
    payload = {
        "mode": _normalize_mode(os.environ.get("NSGABLACK_EXPERIMENT_DB_MODE")),
        "source": None if resolved is None else resolved.source,
        "config_path": None if resolved is None else resolved.config_path,
        "readonly": False if resolved is None else bool(resolved.readonly),
        "db_target": _safe_target_label(target),
        "db_backend": "postgresql" if _is_postgres_target(target) else "sqlite",
        "filesystem_path": None if _is_postgres_target(target) or _is_sqlite_url(target) else str(Path(target).expanduser().resolve()),
        "is_file_backed": not _is_postgres_target(target),
    }
    return payload


def summarize_experiment_db_error(exc: BaseException, *, target: str | None = None) -> dict[str, str]:
    safe_target = _safe_target_label(str(target or "").strip())
    raw_message = " ".join(str(exc or "").split()).strip()
    lower = raw_message.lower()
    sqlstate = str(getattr(exc, "sqlstate", "") or "").strip().upper()
    parsed = urlparse(str(target or "").strip()) if str(target or "").strip() else None
    username = str((parsed.username if parsed is not None else "") or "").strip()

    code = "unknown"
    title = "实验库不可连接 / Experiment DB is unavailable"
    detail = raw_message or exc.__class__.__name__
    hint = "请检查实验库配置、数据库进程和本地回退数据源。 / Check the experiment DB config, the database service, and local fallback sources."

    auth_tokens = ("authentication failed", "password", "28p01", "auth")
    if sqlstate == "28P01" or ("password" in lower and ("failed" in lower or "auth" in lower)) or "authentication failed" in lower:
        code = "auth_failed"
        user_label = f" 用户 {username}" if username else ""
        detail = f"PostgreSQL{user_label} 的密码认证失败 / PostgreSQL password authentication failed."
        hint = (
            "请检查 experiment/db.toml 或环境变量里的 PostgreSQL 用户名与密码；如果本地存在 runs/runtime_surface.sqlite3，页面会继续尝试回退。 / "
            "Check the PostgreSQL user/password in experiment/db.toml or env vars; if a local runs/runtime_surface.sqlite3 exists, the UI can fall back to it."
        )
    elif any(token in lower for token in ("connection refused", "could not connect", "connection failed", "timeout", "timed out", "server closed")):
        code = "connection_failed"
        detail = "数据库连接失败 / Database connection failed."
        hint = (
            "请确认 PostgreSQL 服务是否已启动、端口是否正确，以及本机是否允许当前连接；如果本地存在标准运行文件或 SQLite surface，页面会尝试回退。 / "
            "Check whether PostgreSQL is running, the port is correct, and the host accepts the connection; the UI can fall back to local standard run files or a SQLite surface when available."
        )
    elif _is_postgres_target(str(target or "")) and any(token in lower for token in auth_tokens):
        code = "auth_failed"

    return {
        "code": code,
        "title": f"{title}: {safe_target}" if safe_target else title,
        "detail": detail,
        "hint": hint,
        "raw_message": raw_message,
        "safe_target": safe_target,
    }


@dataclass(frozen=True)
class ExperimentDbTarget:
    raw_target: str
    backend: str
    safe_label: str
    filesystem_path: str | None


def normalize_experiment_db_target(target: str | None) -> ExperimentDbTarget:
    raw = resolve_experiment_db_target(target)
    if _is_postgres_target(raw):
        return ExperimentDbTarget(
            raw_target=raw,
            backend="postgresql",
            safe_label=_safe_target_label(raw),
            filesystem_path=None,
        )
    if _is_sqlite_url(raw):
        parsed = urlparse(raw)
        path = str(parsed.path or "").lstrip("/") or _DEFAULT_SQLITE_TARGET
        resolved_path = str(Path(path).expanduser().resolve())
        return ExperimentDbTarget(raw_target=resolved_path, backend="sqlite", safe_label=resolved_path, filesystem_path=resolved_path)
    resolved_path = str(Path(raw).expanduser().resolve())
    return ExperimentDbTarget(raw_target=resolved_path, backend="sqlite", safe_label=resolved_path, filesystem_path=resolved_path)


class ExperimentDbConnection:
    def __init__(self, target: ExperimentDbTarget) -> None:
        self.target = target
        self.backend = target.backend
        if self.backend == "postgresql":
            if _pg_connect is None:
                raise RuntimeError("PostgreSQL driver missing: install psycopg.")
            parsed = urlparse(target.raw_target)
            kwargs = {
                "host": parsed.hostname or "127.0.0.1",
                "port": int(parsed.port or 5432),
                "user": parsed.username or "postgres",
                "password": parsed.password or "",
                "dbname": (parsed.path or "").lstrip("/") or "postgres",
                "row_factory": _pg_dict_row,
            }
            if parsed.query:
                query_bits = {piece.split("=", 1)[0]: piece.split("=", 1)[1] for piece in parsed.query.split("&") if "=" in piece}
                if "connect_timeout" in query_bits:
                    try:
                        kwargs["connect_timeout"] = int(query_bits["connect_timeout"])
                    except Exception:
                        pass
            self._conn = _pg_connect(**kwargs)
        else:
            db_path = str(target.filesystem_path or target.raw_target)
            Path(db_path).expanduser().resolve().parent.mkdir(parents=True, exist_ok=True)
            conn = sqlite3.connect(db_path)
            conn.row_factory = sqlite3.Row
            self._conn = conn

    def _adapt_sql(self, sql: str) -> str:
        if self.backend != "postgresql":
            return sql
        return str(sql).replace("?", "%s")

    def execute(self, sql: str, params: Sequence[Any] = ()) -> Any:
        return self._conn.execute(self._adapt_sql(sql), tuple(params))

    def commit(self) -> None:
        self._conn.commit()

    def rollback(self) -> None:
        self._conn.rollback()

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> "ExperimentDbConnection":
        return self

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        try:
            if exc_type is not None:
                self.rollback()
        finally:
            self.close()


def open_experiment_db(target: str | None = None) -> ExperimentDbConnection:
    return ExperimentDbConnection(normalize_experiment_db_target(target))


def table_columns(conn: ExperimentDbConnection, table_name: str) -> set[str]:
    if conn.backend == "postgresql":
        rows = conn.execute(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = current_schema() AND table_name = %s
            """,
            (str(table_name),),
        ).fetchall()
        return {str((row.get("column_name") if isinstance(row, Mapping) else row[0])) for row in rows}
    rows = conn.execute(f"PRAGMA table_info({table_name})").fetchall()
    return {str(row[1]) for row in rows}


def ensure_table_columns(conn: ExperimentDbConnection, table_name: str, columns: Mapping[str, str]) -> None:
    existing = table_columns(conn, table_name)
    for name, sql_type in dict(columns).items():
        if str(name) in existing:
            continue
        conn.execute(f"ALTER TABLE {table_name} ADD COLUMN {name} {sql_type}")


def table_exists(conn: ExperimentDbConnection, table_name: str) -> bool:
    if conn.backend == "postgresql":
        row = conn.execute("SELECT to_regclass(%s) AS table_ref", (str(table_name),)).fetchone()
        if row is None:
            return False
        if isinstance(row, Mapping):
            return bool(row.get("table_ref"))
        return bool(row[0])
    row = conn.execute(
        "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name=?",
        (str(table_name),),
    ).fetchone()
    if row is None:
        return False
    if isinstance(row, Mapping):
        return int(next(iter(row.values()))) > 0
    return int(row[0]) > 0


def table_count(conn: ExperimentDbConnection, table_name: str) -> int:
    if not table_exists(conn, table_name):
        return 0
    row = conn.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()
    if row is None:
        return 0
    if isinstance(row, Mapping):
        return int(next(iter(row.values())))
    return int(row[0])


def first_column_texts(rows: Sequence[Any]) -> list[str]:
    out: list[str] = []
    for row in rows:
        if isinstance(row, Mapping):
            value = next(iter(row.values()), None)
        else:
            value = row[0] if row else None
        text = str(value).strip() if value is not None else ""
        if text:
            out.append(text)
    return out


__all__ = [
    "ExperimentDbConnection",
    "ExperimentDbResolvedConfig",
    "ExperimentDbTarget",
    "ensure_table_columns",
    "experiment_db_candidate_targets",
    "experiment_db_config_info",
    "experiment_db_resolved_config",
    "first_column_texts",
    "normalize_experiment_db_target",
    "open_experiment_db",
    "resolve_experiment_db_target",
    "summarize_experiment_db_error",
    "table_columns",
    "table_count",
    "table_exists",
]
