"""L0 Storage — state persistence backends (context, snapshot, artifact, lease).

Re-exports from canonical source modules.
"""

from .lease import (
    DataRef,
    ResourceContext,
    ResourceAudit,
    ResourceEvent,
    coerce_resource_context,
)

# Lazy imports to avoid circular deps during module init
def __getattr__(name: str):
    if name in {"ContextStore", "InMemoryContextStore", "RedisContextStore", "create_context_store"}:
        from nsgablack.core.state.context_store import (  # type: ignore[attr-defined]
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
        from nsgablack.core.state.snapshot_store import (  # type: ignore[attr-defined]
            SnapshotStore, SnapshotHandle, SnapshotRecord,
            InMemorySnapshotStore, RedisSnapshotStore, FileSnapshotStore,
        )
        _g = globals()
        _g["SnapshotStore"] = SnapshotStore
        _g["SnapshotHandle"] = SnapshotHandle
        _g["SnapshotRecord"] = SnapshotRecord
        _g["InMemorySnapshotStore"] = InMemorySnapshotStore
        _g["RedisSnapshotStore"] = RedisSnapshotStore
        _g["FileSnapshotStore"] = FileSnapshotStore
        return _g[name]
    if name in {"ArtifactBackend", "InMemoryArtifactBackend", "FilesystemArtifactBackend"}:
        from nsgablack.core.resources.backends import (  # type: ignore[attr-defined]
            ArtifactBackend, InMemoryArtifactBackend, FilesystemArtifactBackend,
        )
        _g = globals()
        _g["ArtifactBackend"] = ArtifactBackend
        _g["InMemoryArtifactBackend"] = InMemoryArtifactBackend
        _g["FilesystemArtifactBackend"] = FilesystemArtifactBackend
        return _g[name]
    if name == "S3ArtifactBackend":
        from nsgablack.core.resources.backends_s3 import S3ArtifactBackend  # type: ignore[attr-defined]
        globals()["S3ArtifactBackend"] = S3ArtifactBackend
        return S3ArtifactBackend
    if name in {"ResourceAllocator", "ResourceBudgetError", "ResourceLease", "ResourceOffer",
                "ResourcePolicy", "ResourceRequest", "InMemoryLeaseStore", "SQLiteLeaseStore",
                "InMemoryMessageQueue", "SQLiteMessageQueue"}:
        from nsgablack.core.solver_manager import (
            ResourceAllocator, ResourceBudgetError, ResourceLease, ResourceOffer,
            ResourcePolicy, ResourceRequest, InMemoryLeaseStore, SQLiteLeaseStore,
            InMemoryMessageQueue, SQLiteMessageQueue,
        )
        _g = globals()
        _g["ResourceAllocator"] = ResourceAllocator
        _g["ResourceBudgetError"] = ResourceBudgetError
        _g["ResourceLease"] = ResourceLease
        _g["ResourceOffer"] = ResourceOffer
        _g["ResourcePolicy"] = ResourcePolicy
        _g["ResourceRequest"] = ResourceRequest
        _g["InMemoryLeaseStore"] = InMemoryLeaseStore
        _g["SQLiteLeaseStore"] = SQLiteLeaseStore
        _g["InMemoryMessageQueue"] = InMemoryMessageQueue
        _g["SQLiteMessageQueue"] = SQLiteMessageQueue
        return _g[name]
    raise AttributeError(name)


__all__ = [
    "DataRef", "ResourceContext", "ResourceAudit", "ResourceEvent", "coerce_resource_context",
    "ResourceAllocator", "ResourceBudgetError",
    "ResourceLease", "ResourceOffer", "ResourcePolicy", "ResourceRequest",
    "InMemoryLeaseStore", "SQLiteLeaseStore",
    "InMemoryMessageQueue", "SQLiteMessageQueue",
    "ContextStore", "InMemoryContextStore", "RedisContextStore", "create_context_store",
    "SnapshotStore", "SnapshotHandle", "SnapshotRecord",
    "InMemorySnapshotStore", "RedisSnapshotStore", "FileSnapshotStore",
    "ArtifactBackend", "InMemoryArtifactBackend", "FilesystemArtifactBackend",
    "S3ArtifactBackend",
]
