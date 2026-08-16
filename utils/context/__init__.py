"""
Context helpers (canonical keys + minimal evaluation schema + lifecycle + replay).

All symbols are now re-exported from blackbase.context for seamless migration.
Prefer importing from nsgablack.core.state or blackbase.context directly.
"""

from __future__ import annotations

from . import context_keys

from blackbase.context import (
    # Events
    ContextEvent,
    apply_context_event,
    record_context_event,
    replay_context,
    # Contracts
    ContextContract,
    collect_solver_contracts,
    detect_context_conflicts,
    get_component_contract,
    validate_context_contracts,
    # Field governance
    CONTEXT_FIELD_SCHEMA_NAME,
    CONTEXT_FIELD_SCHEMA_VERSION,
    context_field_schema_dict,
    is_canonical_context_key,
    schema_meta,
    # Schema
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
    # Store
    ContextStore,
    InMemoryContextStore,
    RedisContextStore,
    create_context_store,
    # Snapshot
    SnapshotHandle,
    SnapshotRecord,
    SnapshotStore,
    FileSnapshotStore,
    InMemorySnapshotStore,
    RedisSnapshotStore,
    create_snapshot_store,
    make_snapshot_key,
)

__all__ = [
    "context_keys",
    "ContextEvent",
    "apply_context_event",
    "record_context_event",
    "replay_context",
    "ContextContract",
    "collect_solver_contracts",
    "detect_context_conflicts",
    "get_component_contract",
    "validate_context_contracts",
    "CONTEXT_FIELD_SCHEMA_NAME",
    "CONTEXT_FIELD_SCHEMA_VERSION",
    "context_field_schema_dict",
    "is_canonical_context_key",
    "schema_meta",
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
    "ContextStore",
    "InMemoryContextStore",
    "RedisContextStore",
    "create_context_store",
    "SnapshotHandle",
    "SnapshotRecord",
    "SnapshotStore",
    "FileSnapshotStore",
    "InMemorySnapshotStore",
    "RedisSnapshotStore",
    "create_snapshot_store",
    "make_snapshot_key",
]
