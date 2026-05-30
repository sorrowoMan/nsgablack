"""PostgreSQL + pgvector chunk store — reuses catalog PG connection pattern."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Sequence

import numpy as np

from .config import RagConfig

logger = logging.getLogger(__name__)

_TABLE_SQL = """
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS rag_chunks (
    id          TEXT PRIMARY KEY,
    source      TEXT NOT NULL,
    framework   TEXT NOT NULL,
    kind        TEXT,
    tags        TEXT[],
    content     TEXT NOT NULL,
    embedding   vector(512),
    metadata    JSONB DEFAULT '{}'::jsonb,
    indexed_at  TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS rag_chunks_framework_idx ON rag_chunks(framework);
CREATE INDEX IF NOT EXISTS rag_chunks_kind_idx ON rag_chunks(kind);
"""

_HNSW_SQL = """
CREATE INDEX IF NOT EXISTS rag_chunks_embedding_idx
    ON rag_chunks USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 200);
"""


@dataclass
class RagChunk:
    id: str
    source: str
    framework: str
    kind: str | None
    tags: list[str]
    content: str
    metadata: dict = field(default_factory=dict)


@dataclass
class RagResult:
    chunk: RagChunk
    similarity: float


class RagStore:
    """PostgreSQL + pgvector store for RAG chunks.

    Shares the same PG instance as the catalog (NSGABLACK_CATALOG_DB_URL).
    """

    def __init__(self, config: RagConfig | None = None):
        self.config = config or RagConfig()
        self._conn = None

    # ------------------------------------------------------------------
    # Connection (mirrors catalog/store/postgres.py pattern)
    # ------------------------------------------------------------------

    def _get_conn(self):
        if self._conn is None or self._conn.closed:
            from psycopg import connect
            from psycopg.rows import dict_row

            if not self.config.pg_available:
                raise RuntimeError(
                    "PostgreSQL not configured — cannot connect to RAG store. "
                    "Set up the catalog PG config file or NSGABLACK_CATALOG_DB_URL."
                )
            cfg = self.config.nsgablack_pg
            url = cfg.get("url", "")
            if "://" in url:
                # Use URL-based connection
                if url.startswith("postgresql+psycopg"):
                    url = "postgresql" + url.split("://", 1)[1]
                self._conn = connect(url, row_factory=dict_row)
            else:
                # Use field-based connection
                self._conn = connect(
                    host=cfg.get("host", "localhost"),
                    port=int(cfg.get("port", 5432)),
                    user=cfg.get("user", "postgres"),
                    password=cfg.get("password", ""),
                    dbname=cfg.get("database", "postgres"),
                    row_factory=dict_row,
                )
        return self._conn

    def close(self):
        if self._conn and not self._conn.closed:
            self._conn.close()
        self._conn = None

    # ------------------------------------------------------------------
    # Table management
    # ------------------------------------------------------------------

    def init_tables(self) -> bool:
        """Create rag_chunks table and HNSW index. Returns True if ready."""
        conn = self._get_conn()
        try:
            with conn.cursor() as cur:
                try:
                    cur.execute("CREATE EXTENSION IF NOT EXISTS vector")
                except Exception:
                    conn.rollback()
                    logger.warning("pgvector extension not available on PG server — install it first")
                    return False
            conn.commit()
        except Exception:
            conn.rollback()
            return False

        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS rag_chunks (
                        id          TEXT PRIMARY KEY,
                        source      TEXT NOT NULL,
                        framework   TEXT NOT NULL,
                        kind        TEXT,
                        tags        TEXT[],
                        content     TEXT NOT NULL,
                        embedding   vector(512),
                        metadata    JSONB DEFAULT '{}'::jsonb,
                        indexed_at  TIMESTAMPTZ DEFAULT NOW()
                    )
                    """
                )
                cur.execute("CREATE INDEX IF NOT EXISTS rag_chunks_fwk_idx ON rag_chunks(framework)")
                cur.execute("CREATE INDEX IF NOT EXISTS rag_chunks_kind_idx ON rag_chunks(kind)")
            conn.commit()
        except Exception as exc:
            conn.rollback()
            logger.warning("create table failed: %s", exc)
            return False

        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    CREATE INDEX IF NOT EXISTS rag_chunks_embedding_idx
                        ON rag_chunks USING hnsw (embedding vector_cosine_ops)
                        WITH (m = 16, ef_construction = 200)
                    """
                )
            conn.commit()
        except Exception:
            conn.rollback()
            logger.warning("HNSW index unavailable — sequential scan fallback")

        return True

    def drop_tables(self) -> None:
        conn = self._get_conn()
        with conn.cursor() as cur:
            cur.execute("DROP TABLE IF EXISTS rag_chunks CASCADE")
        conn.commit()

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    def insert_batch(
        self,
        chunks: Sequence[RagChunk],
        embeddings: np.ndarray,
    ) -> int:
        if len(chunks) == 0:
            return 0
        if len(chunks) != len(embeddings):
            raise ValueError(f"chunks/embeddings length mismatch: {len(chunks)} vs {len(embeddings)}")

        conn = self._get_conn()
        now = datetime.now(timezone.utc).isoformat()
        count = 0
        with conn.cursor() as cur:
            for chunk, emb in zip(chunks, embeddings):
                cur.execute(
                    """
                    INSERT INTO rag_chunks (id, source, framework, kind, tags, content, embedding, metadata, indexed_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (id) DO UPDATE SET
                        source = EXCLUDED.source,
                        framework = EXCLUDED.framework,
                        kind = EXCLUDED.kind,
                        tags = EXCLUDED.tags,
                        content = EXCLUDED.content,
                        embedding = EXCLUDED.embedding,
                        metadata = EXCLUDED.metadata,
                        indexed_at = EXCLUDED.indexed_at
                    """,
                    (
                        chunk.id,
                        chunk.source,
                        chunk.framework,
                        chunk.kind,
                        list(chunk.tags or []),
                        chunk.content,
                        emb.astype(np.float32).tolist(),
                        json.dumps(chunk.metadata or {}, ensure_ascii=False),
                        now,
                    ),
                )
                count += 1
        conn.commit()
        return count

    def search(
        self,
        query_embedding: np.ndarray,
        *,
        kind: str | None = None,
        tags: list[str] | None = None,
        framework: str | None = None,
        top_k: int = 5,
        threshold: float = 0.5,
    ) -> list[RagResult]:
        try:
            conn = self._get_conn()
        except RuntimeError:
            return []
        emb_list = query_embedding.astype(np.float32).tolist()
        query = """
            SELECT id, source, framework, kind, tags, content, metadata,
                   1 - (embedding <=> %s::vector) AS similarity
            FROM rag_chunks
            WHERE embedding IS NOT NULL
              AND 1 - (embedding <=> %s::vector) >= %s
        """
        params: list[Any] = [emb_list, emb_list, float(threshold)]

        if kind:
            query += " AND kind = %s"
            params.append(kind)
        if framework:
            query += " AND framework = %s"
            params.append(framework)
        if tags:
            query += " AND tags && %s"
            params.append(list(tags))

        query += " ORDER BY embedding <=> %s::vector LIMIT %s"
        params.extend([emb_list, int(top_k)])

        with conn.cursor() as cur:
            cur.execute(query, params)
            rows = cur.fetchall()

        return [
            RagResult(
                chunk=RagChunk(
                    id=row["id"],
                    source=row["source"],
                    framework=row["framework"],
                    kind=row.get("kind"),
                    tags=row.get("tags") or [],
                    content=row["content"],
                    metadata=row.get("metadata") or {},
                ),
                similarity=float(row["similarity"]),
            )
            for row in rows
        ]

    def chunk_count(self, framework: str | None = None) -> int:
        if not self.config.pg_available:
            return 0
        try:
            conn = self._get_conn()
            query = "SELECT COUNT(*) AS cnt FROM rag_chunks"
            params: list[Any] = []
            if framework:
                query += " WHERE framework = %s"
                params.append(framework)
            with conn.cursor() as cur:
                cur.execute(query, params)
                row = cur.fetchone()
            return int(row["cnt"]) if row else 0
        except Exception:
            return 0  # table not created yet

    def last_indexed_at(self) -> str | None:
        if not self.config.pg_available:
            return None
        try:
            conn = self._get_conn()
            with conn.cursor() as cur:
                cur.execute("SELECT MAX(indexed_at) AS ts FROM rag_chunks")
                row = cur.fetchone()
            return str(row["ts"]) if row and row["ts"] else None
        except Exception:
            return None  # table not created yet
