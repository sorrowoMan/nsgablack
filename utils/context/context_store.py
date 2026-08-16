"""Forwarding module for context store (legacy path).

This module re-exports from blackbase for seamless migration.
Prefer importing from nsgablack.core.state.context_store or blackbase.context.
"""

from blackbase.context import (
    ContextStore,
    InMemoryContextStore,
    RedisContextStore,
    create_context_store,
)

__all__ = [
    "ContextStore",
    "InMemoryContextStore",
    "RedisContextStore",
    "create_context_store",
]
