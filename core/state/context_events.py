"""
Forwarding module for context events.

This module re-exports from blackbase for seamless migration.
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