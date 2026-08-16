"""Forwarding module for context schema (legacy path).

This module re-exports from blackbase for seamless migration.
Prefer importing from nsgablack.core.state.context_schema or blackbase.context.
"""

from blackbase.context import (
    CATEGORY_CACHE,
    CATEGORY_DERIVED,
    CATEGORY_EVENT,
    CATEGORY_INPUT,
    CATEGORY_OUTPUT,
    CATEGORY_RUNTIME,
    ContextField,
    ContextSchema,
    MinimalEvaluationContext,
    RUNTIME_CONTEXT_SCHEMA,
    build_minimal_context,
    get_context_lifecycle,
    is_replayable_context,
    strip_context_for_replay,
    validate_context,
    validate_minimal_context,
)

__all__ = [
    "CATEGORY_CACHE",
    "CATEGORY_DERIVED",
    "CATEGORY_EVENT",
    "CATEGORY_INPUT",
    "CATEGORY_OUTPUT",
    "CATEGORY_RUNTIME",
    "ContextField",
    "ContextSchema",
    "MinimalEvaluationContext",
    "RUNTIME_CONTEXT_SCHEMA",
    "build_minimal_context",
    "get_context_lifecycle",
    "is_replayable_context",
    "strip_context_for_replay",
    "validate_context",
    "validate_minimal_context",
]
