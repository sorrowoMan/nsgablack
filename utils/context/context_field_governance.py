from __future__ import annotations

from dataclasses import dataclass
from typing import Dict

from .context_keys import CANONICAL_CONTEXT_KEYS, normalize_context_key


CONTEXT_FIELD_SCHEMA_NAME = "context_field_schema"
CONTEXT_FIELD_SCHEMA_VERSION = 2


@dataclass(frozen=True)
class ContextFieldSchemaMeta:
    schema_name: str
    schema_version: int


def schema_meta() -> ContextFieldSchemaMeta:
    return ContextFieldSchemaMeta(
        schema_name=CONTEXT_FIELD_SCHEMA_NAME,
        schema_version=int(CONTEXT_FIELD_SCHEMA_VERSION),
    )


def is_canonical_context_key(key: str) -> bool:
    text = str(key).strip()
    if not text:
        return False
    normalized = normalize_context_key(text)
    if normalized.startswith("metrics."):
        return True
    return normalized in CANONICAL_CONTEXT_KEYS and normalized == text.lower()


def context_field_schema_dict() -> Dict[str, object]:
    meta = schema_meta()
    return {
        "schema_name": meta.schema_name,
        "schema_version": meta.schema_version,
    }
