"""RAG configuration — embedding model, DB URLs, chunk settings."""

from __future__ import annotations

import os
from importlib.util import find_spec
from dataclasses import dataclass, field
from pathlib import Path


RAG_STORAGE_DIMENSION = 512


def _resolve_rag_database_url() -> str | None:
    """Resolve the dedicated PostgreSQL store used by the optional RAG tool."""

    url = os.environ.get("NSGABLACK_RAG_DB_URL", "").strip()
    return url or None


@dataclass
class RagConfig:
    """Configuration for the RAG indexing and retrieval system."""

    # PostgreSQL.  RAG owns a dedicated operator-store configuration instead of
    # reinterpreting the Catalog URL, which may legitimately target MySQL.
    database_url: str | None = field(default_factory=_resolve_rag_database_url)

    # Embedding
    embedding_model: str = "text-embedding-3-small"
    embedding_dim: int = RAG_STORAGE_DIMENSION
    local_embedding_model: str = "all-MiniLM-L6-v2"

    # Chunking
    max_chunk_tokens: int = 512
    overlap_tokens: int = 50

    # Indexing
    batch_size: int = 20

    # Retrieval
    default_top_k: int = 5
    similarity_threshold: float = 0.2  # Lower for MiniLM; higher (0.5) if using OpenAI

    def __post_init__(self) -> None:
        database_url = str(self.database_url or "").strip()
        if database_url and not database_url.startswith(
            ("postgresql://", "postgresql+psycopg://", "postgres://")
        ):
            raise ValueError(
                "NSGABLACK_RAG_DB_URL must use a PostgreSQL URL scheme"
            )
        self.database_url = database_url or None
        if int(self.embedding_dim) != RAG_STORAGE_DIMENSION:
            raise ValueError(
                "RAG PostgreSQL schema uses a fixed embedding dimension of "
                f"{RAG_STORAGE_DIMENSION}; got {self.embedding_dim}"
            )
        if int(self.batch_size) < 1:
            raise ValueError("RAG batch_size must be positive")
        if int(self.default_top_k) < 1:
            raise ValueError("RAG default_top_k must be positive")
        threshold = float(self.similarity_threshold)
        if not 0.0 <= threshold <= 1.0:
            raise ValueError("RAG similarity_threshold must be within [0, 1]")

    @property
    def pg_available(self) -> bool:
        return self.database_url is not None

    @property
    def pg_url(self) -> str | None:
        return self.database_url


def resolve_framework_root(framework: str) -> Path | None:
    """Resolve one installed/source framework without assuming sibling checkouts."""

    name = str(framework or "").strip()
    if not name or not name.replace("_", "").isalnum():
        raise ValueError(f"invalid framework package name: {framework!r}")
    override = os.environ.get(f"{name.upper()}_ROOT", "").strip()
    if override:
        root = Path(override).expanduser().resolve()
        return root if root.is_dir() else None
    spec = find_spec(name)
    if spec is None:
        return None
    locations = tuple(spec.submodule_search_locations or ())
    if locations:
        package_root = Path(locations[0]).resolve()
    elif spec.origin:
        package_root = Path(spec.origin).resolve().parent
    else:
        return None
    source_root = package_root.parent
    if (source_root / "pyproject.toml").is_file():
        return source_root
    return package_root


__all__ = ["RAG_STORAGE_DIMENSION", "RagConfig", "resolve_framework_root"]
