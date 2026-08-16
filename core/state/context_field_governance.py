"""
Forwarding module for context field governance.

This module re-exports from blackbase for seamless migration.
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