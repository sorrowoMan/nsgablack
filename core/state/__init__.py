"""
Forwarding module for state package.

This module re-exports from blackbase for seamless migration.
"""

from blackbase.context import (
    CONTEXT_KEY_ALIASES,
    CONTEXT_KEY_SET,
    METRIC_FALLBACKS,
    METRIC_KEYS,
    CONTEXT_FIELD_SCHEMA_NAME,
    CONTEXT_FIELD_SCHEMA_VERSION,
    CATEGORY_CACHE,
    CATEGORY_DERIVED,
    CATEGORY_EVENT,
    CATEGORY_INPUT,
    CATEGORY_OUTPUT,
    CATEGORY_RUNTIME,
    ContextContract,
    ContextField,
    ContextSchema,
    ContextStore,
    MinimalEvaluationContext,
    RUNTIME_CONTEXT_SCHEMA,
    SnapshotHandle,
    SnapshotRecord,
    SnapshotStore,
    normalize_context_key,
    normalize_context_keys,
    register_context_keys,
    unknown_context_keys,
    validate_context_keys,
    collect_solver_contracts,
    detect_context_conflicts,
    get_component_contract,
    validate_context_contracts,
    create_context_store,
    create_snapshot_store,
    make_snapshot_key,
    build_minimal_context,
    validate_context,
    validate_minimal_context,
    get_context_lifecycle,
    is_replayable_context,
    strip_context_for_replay,
    context_field_schema_dict,
    is_canonical_context_key,
    schema_meta,
    ContextEvent,
    apply_context_event,
    record_context_event,
    replay_context,
)

__all__ = [
    # Keys
    "CONTEXT_KEY_ALIASES",
    "CONTEXT_KEY_SET",
    "METRIC_FALLBACKS",
    "METRIC_KEYS",
    "normalize_context_key",
    "normalize_context_keys",
    "register_context_keys",
    "unknown_context_keys",
    "validate_context_keys",
    
    # Contracts
    "ContextContract",
    "collect_solver_contracts",
    "detect_context_conflicts",
    "get_component_contract",
    "validate_context_contracts",
    
    # Store
    "ContextStore",
    "create_context_store",
    
    # Snapshot
    "SnapshotStore",
    "SnapshotHandle",
    "SnapshotRecord",
    "create_snapshot_store",
    "make_snapshot_key",
    
    # Schema
    "ContextField",
    "ContextSchema",
    "MinimalEvaluationContext",
    "RUNTIME_CONTEXT_SCHEMA",
    "build_minimal_context",
    "validate_context",
    "validate_minimal_context",
    "get_context_lifecycle",
    "is_replayable_context",
    "strip_context_for_replay",
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
    
    # Events
    "ContextEvent",
    "apply_context_event",
    "record_context_event",
    "replay_context",
]