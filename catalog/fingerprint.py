from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from typing import Iterable


CATALOG_SOURCE_SCHEMA = "nsgablack.catalog.source.v3"

_SOURCE_FIELDS = (
    "key",
    "title",
    "kind",
    "import_path",
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
    "contract",
    "metadata",
)


def _json_value(value: object) -> object:
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, (list, tuple)):
        return [_json_value(item) for item in value]
    if isinstance(value, Mapping):
        return {str(key): _json_value(item) for key, item in value.items()}
    return str(value)


def catalog_entries_digest(entries: Iterable[object]) -> str:
    """Return the stable semantic identity of one materialized Catalog source.

    Public semantic metadata is included alongside the component contract.
    Database transport metadata and timestamps are not CatalogEntry fields and
    remain excluded. A cache is valid only while its published source matches.
    """

    records = []
    for entry in entries:
        records.append(
            {
                field: _json_value(getattr(entry, field, None))
                for field in _SOURCE_FIELDS
            }
        )
    records.sort(key=lambda item: str(item.get("key", "")))
    payload = {
        "schema": CATALOG_SOURCE_SCHEMA,
        "entries": records,
    }
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


__all__ = ["CATALOG_SOURCE_SCHEMA", "catalog_entries_digest"]
