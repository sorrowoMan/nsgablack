"""Optimization-facing public snapshot-store surface backed by blackbase."""

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
