"""L0 Storage — state persistence backends (context, snapshot, artifact, lease).

Re-exports from canonical source modules.
"""

from .lease import (
    ResourceAllocator, ResourceBudgetError, ResourceEvent,
    ResourceLease, ResourceOffer, ResourcePolicy, ResourceRequest,
    InMemoryLeaseStore, SQLiteLeaseStore,
    InMemoryMessageQueue, SQLiteMessageQueue,
)

# Lazy imports to avoid circular deps during module init
def __getattr__(name: str):
    if name in {"ContextStore", "InMemoryContextStore", "RedisContextStore", "create_context_store"}:
        from nsgablack.utils.context.context_store import (  # type: ignore[attr-defined]
            ContextStore, InMemoryContextStore, RedisContextStore, create_context_store,
        )
        _g = globals()
        _g["ContextStore"] = ContextStore
        _g["InMemoryContextStore"] = InMemoryContextStore
        _g["RedisContextStore"] = RedisContextStore
        _g["create_context_store"] = create_context_store
        return _g[name]
    if name in {"SnapshotStore", "SnapshotHandle", "SnapshotRecord", "InMemorySnapshotStore",
                "RedisSnapshotStore", "FileSnapshotStore"}:
        from nsgablack.utils.context.snapshot_store import (  # type: ignore[attr-defined]
            SnapshotStore, SnapshotHandle, SnapshotRecord,
            InMemorySnapshotStore, RedisSnapshotStore, FileSnapshotStore,
        )
        _g = globals()
        for n in ("SnapshotStore", "SnapshotHandle", "SnapshotRecord",
                   "InMemorySnapshotStore", "RedisSnapshotStore", "FileSnapshotStore"):
            if n in locals():
                _g[n] = locals()[n]
        return _g[name]
    if name in {"ArtifactBackend", "InMemoryArtifactBackend", "FilesystemArtifactBackend"}:
        from nsgablack.core.resources.backends import (  # type: ignore[attr-defined]
            ArtifactBackend, InMemoryArtifactBackend, FilesystemArtifactBackend,
        )
        _g = globals()
        for n in ("ArtifactBackend", "InMemoryArtifactBackend", "FilesystemArtifactBackend"):
            if n in locals():
                _g[n] = locals()[n]
        return _g[name]
    if name == "S3ArtifactBackend":
        from nsgablack.core.resources.backends_s3 import S3ArtifactBackend  # type: ignore[attr-defined]
        globals()["S3ArtifactBackend"] = S3ArtifactBackend
        return S3ArtifactBackend
    raise AttributeError(name)


__all__ = [
    "ResourceAllocator", "ResourceBudgetError", "ResourceEvent",
    "ResourceLease", "ResourceOffer", "ResourcePolicy", "ResourceRequest",
    "InMemoryLeaseStore", "SQLiteLeaseStore",
    "InMemoryMessageQueue", "SQLiteMessageQueue",
    "ContextStore", "InMemoryContextStore", "RedisContextStore", "create_context_store",
    "SnapshotStore", "SnapshotHandle", "SnapshotRecord",
    "InMemorySnapshotStore", "RedisSnapshotStore", "FileSnapshotStore",
    "ArtifactBackend", "InMemoryArtifactBackend", "FilesystemArtifactBackend",
    "S3ArtifactBackend",
]
