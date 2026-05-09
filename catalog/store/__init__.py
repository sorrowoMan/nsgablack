"""Catalog storage backends."""

from __future__ import annotations

import os
from typing import Any
from urllib.parse import urlparse

from .mysql import MySQLCatalogConfig, MySQLCatalogStore, mysql_config_enabled, mysql_config_info, mysql_config_mode, parse_mysql_url
from .postgres import (
    PostgresCatalogConfig,
    PostgresCatalogStore,
    postgres_config_enabled,
    postgres_config_info,
    postgres_config_mode,
    parse_postgres_url,
)


def _url_backend(url: str | None) -> str | None:
    raw = str(url or "").strip()
    if not raw:
        return None
    try:
        scheme = str(urlparse(raw).scheme or "").strip().lower()
    except Exception:
        return None
    if scheme in {"mysql", "mysql+pymysql", "mysql+mysqlconnector"}:
        return "mysql"
    if scheme in {"postgres", "postgresql", "postgresql+psycopg", "postgresql+psycopg2"}:
        return "postgresql"
    return None


def _env_db_url() -> str:
    return str(os.environ.get("NSGABLACK_CATALOG_DB_URL", "") or "").strip()


def resolve_catalog_store(url: str | None = None, *, readonly: bool | None = None) -> Any:
    target = str(url or "").strip()
    backend = _url_backend(target)
    if target:
        if backend == "mysql":
            return MySQLCatalogStore(url=target, readonly=readonly)
        if backend == "postgresql":
            return PostgresCatalogStore(url=target, readonly=readonly)
        raise ValueError(f"Unsupported catalog DB URL scheme: {target}")

    env_url = _env_db_url()
    env_backend = _url_backend(env_url)
    if env_backend == "mysql":
        return MySQLCatalogStore(readonly=readonly)
    if env_backend == "postgresql":
        return PostgresCatalogStore(readonly=readonly)

    if postgres_config_enabled():
        return PostgresCatalogStore(readonly=readonly)
    if mysql_config_enabled():
        return MySQLCatalogStore(readonly=readonly)
    raise RuntimeError("Catalog DB config missing. Set NSGABLACK_CATALOG_DB_URL or enable catalog/db.toml.")


def catalog_db_config_enabled() -> bool:
    env_backend = _url_backend(_env_db_url())
    if env_backend is not None:
        return True
    return bool(mysql_config_enabled() or postgres_config_enabled())


def catalog_db_config_backend() -> str | None:
    env_backend = _url_backend(_env_db_url())
    if env_backend is not None:
        return env_backend
    if postgres_config_enabled():
        return "postgresql"
    if mysql_config_enabled():
        return "mysql"
    return None


def catalog_db_config_mode() -> str:
    env_mode = str(os.environ.get("NSGABLACK_CATALOG_DB_MODE", "") or "").strip().lower()
    if env_mode in {"only", "prefer", "off", "disabled"}:
        return "off" if env_mode == "disabled" else env_mode
    backend = catalog_db_config_backend()
    if backend == "mysql":
        return mysql_config_mode()
    if backend == "postgresql":
        return postgres_config_mode()
    return "prefer"


def catalog_db_config_info() -> dict[str, object]:
    backend = catalog_db_config_backend()
    if backend == "mysql":
        info = dict(mysql_config_info())
    elif backend == "postgresql":
        info = dict(postgres_config_info())
    else:
        info = {
            "enabled": False,
            "mode": catalog_db_config_mode(),
            "backend": None,
            "config_env": str(os.environ.get("NSGABLACK_CATALOG_DB_CONFIG", "") or "").strip() or None,
            "explicit_url_env": False,
            "readonly": False,
        }
    info["backend"] = backend
    info["mysql_enabled"] = bool(mysql_config_enabled())
    info["postgres_enabled"] = bool(postgres_config_enabled())
    return info


__all__ = [
    "MySQLCatalogStore",
    "MySQLCatalogConfig",
    "parse_mysql_url",
    "PostgresCatalogStore",
    "PostgresCatalogConfig",
    "parse_postgres_url",
    "resolve_catalog_store",
    "catalog_db_config_enabled",
    "catalog_db_config_mode",
    "catalog_db_config_backend",
    "catalog_db_config_info",
]
