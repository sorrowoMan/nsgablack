"""Forwarding module for snapshot store (legacy path).

This module re-exports from blackbase for seamless migration.
Prefer importing from nsgablack.core.state.snapshot_store or blackbase.context.
"""

from blackbase.context import (
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
    "SnapshotHandle",
    "SnapshotRecord",
    "SnapshotStore",
    "FileSnapshotStore",
    "InMemorySnapshotStore",
    "RedisSnapshotStore",
    "create_snapshot_store",
    "make_snapshot_key",
]
