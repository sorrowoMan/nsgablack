"""Schema version helpers for JSON artifacts."""

from __future__ import annotations

from typing import Any, Dict, Mapping, Tuple


SCHEMA_VERSIONS: Dict[str, int] = {
    "run_inspector_snapshot": 1,
    "module_report": 1,
    "bias_report": 1,
    "benchmark_summary": 1,
}


class SchemaVersionError(ValueError):
    """Raised when artifact schema is missing or incompatible."""


def expected_schema_version(schema_name: str) -> int:
    key = str(schema_name).strip()
    if key not in SCHEMA_VERSIONS:
        raise KeyError(f"Unknown schema name: {schema_name!r}")
    return int(SCHEMA_VERSIONS[key])


def stamp_schema(payload: Mapping[str, Any], schema_name: str, *, version: int | None = None) -> Dict[str, Any]:
    out = dict(payload)
    out["schema_name"] = str(schema_name).strip()
    out["schema_version"] = int(version if version is not None else expected_schema_version(schema_name))
    return out


def schema_check(payload: Mapping[str, Any], schema_name: str) -> Tuple[bool, str]:
    expected = expected_schema_version(schema_name)
    got_name = str(payload.get("schema_name", "") or "").strip()
    if got_name and got_name != schema_name:
        return False, f"schema_name mismatch: got={got_name!r}, expected={schema_name!r}"
    got_ver = int(payload.get("schema_version", 0) or 0)
    if got_ver != expected:
        return False, f"schema_version mismatch: got={got_ver}, expected={expected}"
    return True, "ok"


def require_schema(payload: Mapping[str, Any], schema_name: str) -> None:
    ok, msg = schema_check(payload, schema_name)
    if not ok:
        raise SchemaVersionError(msg)
