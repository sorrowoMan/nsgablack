"""Forwarding module for context field governance (legacy path).

This module re-exports from blackbase for seamless migration.
Prefer importing from nsgablack.core.state.context_field_governance or blackbase.context.
"""

from blackbase.context import (
    CONTEXT_FIELD_SCHEMA_NAME,
    CONTEXT_FIELD_SCHEMA_VERSION,
    context_field_schema_dict,
    is_canonical_context_key,
    schema_meta,
)

__all__ = [
    "CONTEXT_FIELD_SCHEMA_NAME",
    "CONTEXT_FIELD_SCHEMA_VERSION",
    "context_field_schema_dict",
    "is_canonical_context_key",
    "schema_meta",
]
