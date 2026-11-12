#!/usr/bin/env python3
"""Private container entrypoint for the existing Catalog UI and materializer."""
from __future__ import annotations

import argparse
from contextlib import redirect_stdout
import io
import ipaddress
import json
import os
from pathlib import Path
import re
import sys
from typing import Mapping, MutableMapping
from urllib.parse import quote
from urllib.request import urlopen


class RuntimeConfigError(RuntimeError):
    pass


def load_mysql_config(path: str | None) -> dict[str, object]:
    if not path:
        raise RuntimeConfigError("Catalog database config file is required")
    try:
        source = Path(path)
        if not source.is_file() or source.stat().st_size > 16384:
            raise RuntimeConfigError("Catalog database config must be a JSON file of at most 16 KiB")
        config = json.loads(source.read_text(encoding="utf-8"))
    except RuntimeConfigError:
        raise
    except (OSError, ValueError, UnicodeError):
        raise RuntimeConfigError("Catalog database config cannot be read as JSON") from None
    return validate_mysql_config(config)


def validate_mysql_config(config: object) -> dict[str, object]:
    if not isinstance(config, dict):
        raise RuntimeConfigError("Catalog database config must be an object")
    required = {"host", "port", "database", "user", "password"}
    if not required <= config.keys() or config.keys() - required - {"backend"}:
        raise RuntimeConfigError("Catalog database config requires host, port, database, user and password")
    if config.get("backend", "mysql") != "mysql":
        raise RuntimeConfigError("This Catalog deployment accepts only a MySQL database")
    for field in ("host", "database", "user", "password"):
        if not isinstance(config[field], str) or not config[field]:
            raise RuntimeConfigError(f"Catalog database config field {field} must be a nonempty string")
    port = config["port"]
    if type(port) is not int or not 1 <= port <= 65535:
        raise RuntimeConfigError("Catalog database port must be an integer from 1 to 65535")
    host = str(config["host"])
    if ":" in host:
        try:
            ipaddress.IPv6Address(host)
        except ValueError:
            raise RuntimeConfigError("Catalog database host is invalid") from None
    elif not re.fullmatch(r"[A-Za-z0-9_.-]+", host):
        raise RuntimeConfigError("Catalog database host is invalid")
    return dict(config)


def mysql_url(config: Mapping[str, object]) -> str:
    config = validate_mysql_config(dict(config))
    host = str(config["host"])
    if ":" in host:
        host = f"[{host}]"
    return (f"mysql://{quote(str(config['user']), safe='')}:{quote(str(config['password']), safe='')}"
            f"@{host}:{config['port']}/{quote(str(config['database']), safe='')}")


def hosted_source(environment: Mapping[str, str]) -> str:
    source = str(environment.get("NSGABLACK_CATALOG_HOSTED_SOURCE", "registry")).strip().lower()
    if source not in {"registry", "database"}:
        raise RuntimeConfigError("NSGABLACK_CATALOG_HOSTED_SOURCE must be registry or database")
    return source


def configure_reader(environment: MutableMapping[str, str]) -> str:
    """Choose only deployment-owned configuration, never browser URL values."""
    source = hosted_source(environment)
    mode = "off"
    if source == "database":
        config = load_mysql_config(environment.get("NSGABLACK_CATALOG_READER_CONFIG"))
        environment["NSGABLACK_CATALOG_DB_URL"] = mysql_url(config)
        mode = "only"
    else:
        environment.pop("NSGABLACK_CATALOG_DB_URL", None)
    environment["NSGABLACK_CATALOG_HOSTED"] = "1"
    environment["NSGABLACK_CATALOG_DB_MODE"] = mode
    environment["NSGABLACK_CATALOG_DB_READONLY"] = "1"
    return mode


def base_url_path(environment: Mapping[str, str]) -> str:
    value = str(environment.get("STREAMLIT_SERVER_BASE_URL_PATH", "")).strip("/")
    if value and (not re.fullmatch(r"[A-Za-z0-9._~/-]+", value)
                  or any(part in {"", ".", ".."} for part in value.split("/"))):
        raise RuntimeConfigError("Streamlit base URL path must contain ordinary path segments")
    return value


def server_port(environment: Mapping[str, str]) -> int:
    try:
        port = int(environment.get("STREAMLIT_SERVER_PORT", "8501"))
    except (TypeError, ValueError):
        raise RuntimeConfigError("Streamlit server port must be an integer") from None
    if not 1 <= port <= 65535:
        raise RuntimeConfigError("Streamlit server port is out of range")
    return port


def health_url(environment: Mapping[str, str]) -> str:
    prefix = base_url_path(environment)
    return f"http://127.0.0.1:{server_port(environment)}/" + (f"{prefix}/" if prefix else "") + "_stcore/health"


def serve() -> int:
    mode = configure_reader(os.environ)
    os.environ["STREAMLIT_SERVER_BASE_URL_PATH"] = base_url_path(os.environ)
    Path(os.environ.get("HOME", "/tmp/catalog")).mkdir(parents=True, exist_ok=True)
    from nsgablack.catalog.dashboard import build_streamlit_command

    command = build_streamlit_command(profile="default", kind="all", scope="framework", source_mode=mode,
                                      headless=True, host="0.0.0.0", port=server_port(os.environ))
    os.execv(sys.executable, command)
    return 0


def sync() -> dict[str, object]:
    """Publish the MySQL full source once, then verify both supported profiles."""
    config = load_mysql_config(os.environ.get("NSGABLACK_CATALOG_WRITER_CONFIG"))
    target = mysql_url(config)
    from nsgablack.catalog.fingerprint import catalog_entries_digest
    from nsgablack.catalog.registry import get_source_catalog
    from nsgablack.catalog.store import resolve_catalog_store
    from nsgablack.catalog.sync import materialize_catalog_to_db

    result = materialize_catalog_to_db(profile="default", runtime=False, db_url=target)
    store = resolve_catalog_store(url=target, readonly=True)
    profiles = {}
    for profile in ("default", "framework-core"):
        source = get_source_catalog(refresh=True, profile=profile).list()
        published = store.list_catalog_entries(profile=profile, limit=None)
        source_keys = sorted(entry.key for entry in source)
        database_keys = sorted(entry.key for entry in published)
        if source_keys != database_keys or len(set(database_keys)) != len(database_keys):
            raise RuntimeConfigError(f"Catalog publication key mismatch for {profile}")
        source_digest = catalog_entries_digest(source)
        database_digest = catalog_entries_digest(published)
        if source_digest != database_digest:
            raise RuntimeConfigError(f"Catalog publication content mismatch for {profile}")
        profiles[profile] = {"total": len(published), "source_digest": source_digest,
                             "database_digest": database_digest,
                             "mlblack_total": sum(entry.metadata.get("catalog_framework") == "mlblack" for entry in published)}
    report = {"ok": True, "backend": "mysql", "components": int(result["components"]), "profiles": profiles}
    if os.environ.get("NSGABLACK_CATALOG_CURATE_ON_SYNC") == "1":
        report["knowledge"] = {"status": "not_started", "reason": "explicit_execution_required",
            "command": "python /opt/catalog/runtime.py curate --execute --keys <key1,key2>"}
    return report


def curate(*, limit: int = 20, workers: int = 3, keys: str | None = None,
           execute: bool = False) -> dict[str, object]:
    """The isolated writer grant publishes explanations; the web reader has no key."""
    if execute is not True or not isinstance(keys, str):
        raise RuntimeConfigError("Paid curation requires explicit --execute and non-empty --keys")
    selected = tuple(dict.fromkeys(key.strip() for key in keys.split(",") if key.strip()))
    if not selected:
        raise RuntimeConfigError("Paid curation requires explicit --execute and non-empty --keys")
    config = load_mysql_config(os.environ.get("NSGABLACK_CATALOG_WRITER_CONFIG"))
    os.environ["NSGABLACK_CATALOG_DB_URL"] = mysql_url(config)
    from nsgablack.catalog.curate import curate_packets, load_packets
    from nsgablack.catalog.curation_provider import DeepSeekGenerator, load_deepseek_config
    from nsgablack.catalog.curation_store import resolve_knowledge_store
    from nsgablack.catalog.examples import load_example_index
    packets = load_packets(Path("/opt/catalog/knowledge-packets.json"),
                           index_path=Path("/opt/catalog/knowledge-sources.json"))
    if set(selected) - set(packets):
        raise RuntimeConfigError("Requested knowledge entry does not exist in this release")
    provider = load_deepseek_config(os.environ.get("NSGABLACK_CATALOG_AI_CONFIG", "/run/secrets/deepseek.json"))
    # Earlier explanation-only deployments used a 2K response budget. Detailed
    # examples and variants need enough space; keep the private credential file
    # unchanged and scope this generation budget to the Catalog publisher.
    from dataclasses import replace
    provider = replace(provider, max_output_tokens=max(provider.max_output_tokens, 12288), timeout_seconds=120)
    store = resolve_knowledge_store(readonly=False)
    store.ensure_schema()
    return curate_packets(packets, store, DeepSeekGenerator(provider, allow_paid_requests=True), model=provider.model,
                          limit=limit, workers=workers, keys=selected,
                          examples_index=load_example_index(Path('/opt/catalog/examples.json')),
                          source_roots={name: Path('/opt/src') / name for name in ('nsgablack','blackbase','mlblack')})


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", nargs="?", choices=("serve", "sync", "curate", "health"), default="serve")
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--workers", type=int, default=3)
    parser.add_argument("--keys")
    parser.add_argument("--execute", action="store_true", help="explicitly authorize paid curation for --keys")
    args = parser.parse_args(argv)
    if args.execute and args.command != "curate":
        parser.error("--execute is only accepted with curate; sync does not start paid work")
    if args.command == "curate" and (not args.execute or not args.keys or not any(key.strip() for key in args.keys.split(","))):
        parser.error("curate requires --execute and non-empty --keys; no paid work was started")
    try:
        if args.command == "serve":
            return serve()
        if args.command == "health":
            with urlopen(health_url(os.environ), timeout=3) as response:
                if response.status != 200 or response.read(32).strip() != b"ok":
                    raise RuntimeConfigError("Catalog health endpoint is not ready")
            return 0
        with redirect_stdout(io.StringIO()):
            result = curate(limit=args.limit, workers=args.workers, keys=args.keys, execute=True) if args.command == "curate" else sync()
        print(json.dumps(result, ensure_ascii=False, separators=(",", ":")))
        return 0 if result["ok"] else 1
    except RuntimeConfigError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
    except Exception as exc:
        # Driver exceptions may contain a URL or configuration; never print them.
        print(json.dumps({"ok": False, "error": "Catalog runtime failed", "error_type": type(exc).__name__}),
              file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
