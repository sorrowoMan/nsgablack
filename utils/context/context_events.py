"""Forwarding module for context events (legacy path).

This module re-exports from blackbase for seamless migration.
Prefer importing from nsgablack.core.state.context_events or blackbase.context.
"""

from blackbase.context import (
    ContextEvent,
    apply_context_event,
    record_context_event,
    replay_context,
)

__all__ = [
    "ContextEvent",
    "apply_context_event",
    "record_context_event",
    "replay_context",
]
