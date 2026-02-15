"""
Context helpers (canonical keys + minimal evaluation schema + lifecycle + replay).

Recommended imports:
- `from nsgablack.utils.context import context_keys as CK`
- `from nsgablack.utils.context.context_schema import build_minimal_context`
"""

from __future__ import annotations

from . import context_keys
from .context_events import ContextEvent, apply_context_event, record_context_event, replay_context
from .context_contracts import (
    ContextContract,
    collect_solver_contracts,
    get_component_contract,
    validate_context_contracts,
)
from .context_schema import (
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
    "context_keys",
    "ContextEvent",
    "apply_context_event",
    "record_context_event",
    "replay_context",
    "ContextContract",
    "collect_solver_contracts",
    "get_component_contract",
    "validate_context_contracts",
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
