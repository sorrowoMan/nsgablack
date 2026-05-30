"""RAG configuration — embedding model, DB URLs, chunk settings."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any


def _resolve_nsgablack_pg_config() -> dict[str, Any] | None:
    """Resolve nsgablack PG connection using the same logic as catalog."""
    try:
        from nsgablack.catalog.store.postgres import _resolve_postgres_config

        url, cfg, _readonly = _resolve_postgres_config()
        if cfg is not None:
            return {
                "host": cfg.host,
                "port": int(cfg.port),
                "user": cfg.user,
                "password": cfg.password,
                "database": cfg.database,
                "url": url or f"postgresql://{cfg.user}:{cfg.password}@{cfg.host}:{cfg.port}/{cfg.database}",
            }
    except Exception:
        pass
    return None


def _resolve_mlblack_pg_config() -> dict[str, Any] | None:
    """Resolve mlblack PG connection — tries env var first, then config file."""
    env_url = os.environ.get("MLBLACK_CATALOG_DB_URL", "").strip()
    if env_url:
        return {"url": env_url}

    try:
        from mlblack.catalog.store.surface import _resolve_postgres_url

        url = _resolve_postgres_url()
        if url:
            return {"url": url}
    except Exception:
        pass
    return None


@dataclass
class RagConfig:
    """Configuration for the RAG indexing and retrieval system."""

    # PostgreSQL — resolved same way as catalog
    nsgablack_pg: dict[str, Any] | None = field(default_factory=_resolve_nsgablack_pg_config)
    mlblack_pg: dict[str, Any] | None = field(default_factory=_resolve_mlblack_pg_config)

    # Embedding
    embedding_model: str = "text-embedding-3-small"
    embedding_dim: int = 512
    local_embedding_model: str = "all-MiniLM-L6-v2"

    # Chunking
    max_chunk_tokens: int = 512
    overlap_tokens: int = 50

    # Indexing
    batch_size: int = 20

    # Retrieval
    default_top_k: int = 5
    similarity_threshold: float = 0.2  # Lower for MiniLM; higher (0.5) if using OpenAI

    @property
    def pg_available(self) -> bool:
        return self.nsgablack_pg is not None

    @property
    def pg_url(self) -> str | None:
        if self.nsgablack_pg is None:
            return None
        return self.nsgablack_pg.get("url")


# Framework root paths for source file resolution
_HERE = os.path.dirname(os.path.abspath(__file__))
NSGABLACK_ROOT = os.environ.get(
    "NSGABLACK_ROOT",
    os.path.dirname(os.path.dirname(_HERE)),  # rag/ -> nsgablack/ -> repo root
)
MLBLACK_ROOT = os.environ.get(
    "MLBLACK_ROOT",
    os.path.join(os.path.dirname(NSGABLACK_ROOT), "mlblack"),
)
