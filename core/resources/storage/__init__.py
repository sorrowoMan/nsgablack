"""L0 Storage — state persistence backends (context, snapshot, artifact, lease).

Re-exports from canonical source modules. Use ``from nsgablack.core.resources.storage import ContextStore`` etc.
"""

from nsgablack.utils.context.context_store import (  # type: ignore[attr-defined]
    ContextStore,
    InMemoryContextStore,
    RedisContextStore,
    create_context_store,
)
from nsgablack.utils.context.snapshot_store import (  # type: ignore[attr-defined]
    SnapshotStore,
    SnapshotHandle,
    SnapshotRecord,
    InMemorySnapshotStore,
    RedisSnapshotStore,
    FileSnapshotStore,
)
from nsgablack.core.resources.backends import (  # type: ignore[attr-defined]
    ArtifactBackend,
    InMemoryArtifactBackend,
    FilesystemArtifactBackend,
)
from nsgablack.core.resources.backends_s3 import S3ArtifactBackend  # type: ignore[attr-defined]
from nsgablack.core.solver_manager import (  # type: ignore[attr-defined]
    ResourceAllocator,
    ResourceLease,
    ResourceOffer,
    ResourceRequest,
    ResourcePolicy,
    ResourceBudgetError,
    InMemoryLeaseStore,
    SQLiteLeaseStore,
)

__all__ = [
    "ContextStore",
    "InMemoryContextStore",
    "RedisContextStore",
    "create_context_store",
    "SnapshotStore",
    "SnapshotHandle",
    "SnapshotRecord",
    "InMemorySnapshotStore",
    "RedisSnapshotStore",
    "FileSnapshotStore",
    "ArtifactBackend",
    "InMemoryArtifactBackend",
    "FilesystemArtifactBackend",
    "S3ArtifactBackend",
    "ResourceAllocator",
    "ResourceLease",
    "ResourceOffer",
    "ResourceRequest",
    "ResourcePolicy",
    "ResourceBudgetError",
    "InMemoryLeaseStore",
    "SQLiteLeaseStore",
]
