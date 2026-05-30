"""PostgreSQL chunk store — pgvector preferred, native PG array fallback."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, List, Sequence

import numpy as np

from .config import RagConfig

logger = logging.getLogger(__name__)

_TABLE_SQL_VECTOR = """
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
CREATE INDEX IF NOT EXISTS rag_chunks_fwk_idx ON rag_chunks(framework);
CREATE INDEX IF NOT EXISTS rag_chunks_kind_idx ON rag_chunks(kind);
"""

_TABLE_SQL_NATIVE = """
CREATE TABLE IF NOT EXISTS rag_chunks (
    id          TEXT PRIMARY KEY,
    source      TEXT NOT NULL,
    framework   TEXT NOT NULL,
    kind        TEXT,
    tags        TEXT[],
    content     TEXT NOT NULL,
    embedding   double precision[],
    metadata    JSONB DEFAULT '{}'::jsonb,
    indexed_at  TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS rag_chunks_fwk_idx ON rag_chunks(framework);
CREATE INDEX IF NOT EXISTS rag_chunks_kind_idx ON rag_chunks(kind);
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
    """PostgreSQL store for RAG chunks.

    Uses pgvector extension if available (HNSW index, fast ANN).
    Falls back to native PG double precision[] with Python cosine similarity.
    """

    def __init__(self, config: RagConfig | None = None):
        self.config = config or RagConfig()
        self._conn = None
        self._has_vector = False  # set by init_tables()

    # ------------------------------------------------------------------
    # Connection
    # ------------------------------------------------------------------

    def _get_conn(self):
        if self._conn is None or self._conn.closed:
            from psycopg import connect
            from psycopg.rows import dict_row

            if not self.config.pg_available:
                raise RuntimeError("PG not configured — check catalog PG config")
            cfg = self.config.nsgablack_pg
            url = cfg.get("url", "")
            if "://" in url:
                if url.startswith("postgresql+psycopg"):
                    url = "postgresql" + url.split("://", 1)[1]
                self._conn = connect(url, row_factory=dict_row)
            else:
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
        """Create rag_chunks table. Tries pgvector first, falls back to native array."""
        conn = self._get_conn()

        # Try pgvector
        try:
            conn.autocommit = True
            with conn.cursor() as cur:
                cur.execute("CREATE EXTENSION IF NOT EXISTS vector")
            conn.autocommit = False
        except Exception:
            conn.rollback()
            conn.autocommit = False

        # Check if vector type exists
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT 1 FROM pg_type WHERE typname = 'vector'")
                has_vector = cur.fetchone() is not None
        except Exception:
            has_vector = False

        self._has_vector = has_vector
        sql = _TABLE_SQL_VECTOR if has_vector else _TABLE_SQL_NATIVE

        try:
            with conn.cursor() as cur:
                cur.execute(sql)
            conn.commit()
            if has_vector:
                self._try_hnsw_index()
            return True
        except Exception as exc:
            conn.rollback()
            logger.warning("init_tables failed: %s", exc)
            return False

    def _try_hnsw_index(self):
        try:
            conn = self._get_conn()
            with conn.cursor() as cur:
                cur.execute(
                    """
                    CREATE INDEX IF NOT EXISTS rag_chunks_emb_idx
                        ON rag_chunks USING hnsw (embedding vector_cosine_ops)
                        WITH (m = 16, ef_construction = 200)
                    """
                )
            conn.commit()
        except Exception:
            logger.debug("HNSW index unavailable")

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
            raise ValueError(
                f"chunks/embeddings length mismatch: {len(chunks)} vs {len(embeddings)}"
            )

        conn = self._get_conn()
        now = datetime.now(timezone.utc).isoformat()
        count = 0

        with conn.cursor() as cur:
            for chunk, emb in zip(chunks, embeddings):
                if self._has_vector:
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
                            chunk.id, chunk.source, chunk.framework,
                            chunk.kind, list(chunk.tags or []), chunk.content,
                            emb.astype(np.float32).tolist(),
                            json.dumps(chunk.metadata or {}, ensure_ascii=False),
                            now,
                        ),
                    )
                else:
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
                            chunk.id, chunk.source, chunk.framework,
                            chunk.kind, list(chunk.tags or []), chunk.content,
                            emb.astype(np.float64).tolist(),
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
        conn = self._get_conn()

        if self._has_vector:
            return self._search_pgvector(
                conn, query_embedding, kind, tags, framework, top_k, threshold
            )
        return self._search_native(
            conn, query_embedding, kind, tags, framework, top_k, threshold
        )

    def _search_pgvector(
        self, conn, q_emb, kind, tags, framework, top_k, threshold
    ) -> list[RagResult]:
        emb_list = q_emb.astype(np.float32).tolist()
        query = """
            SELECT id, source, framework, kind, tags, content, metadata,
                   1 - (embedding <=> %s::vector) AS similarity
            FROM rag_chunks
            WHERE embedding IS NOT NULL
              AND 1 - (embedding <=> %s::vector) >= %s
        """
        params: list[Any] = [emb_list, emb_list, float(threshold)]
        if kind:
            query += " AND kind = %s"; params.append(kind)
        if framework:
            query += " AND framework = %s"; params.append(framework)
        if tags:
            query += " AND tags && %s"; params.append(list(tags))
        query += " ORDER BY embedding <=> %s::vector LIMIT %s"
        params.extend([emb_list, int(top_k)])

        with conn.cursor() as cur:
            cur.execute(query, params)
            rows = cur.fetchall()
        return self._rows_to_results(rows)

    def _search_native(
        self, conn, q_emb, kind, tags, framework, top_k, threshold
    ) -> list[RagResult]:
        """Python cosine similarity. Load matching rows, compare in memory."""
        query = """
            SELECT id, source, framework, kind, tags, content, embedding, metadata
            FROM rag_chunks
            WHERE embedding IS NOT NULL
        """
        params: list[Any] = []
        if kind:
            query += " AND kind = %s"; params.append(kind)
        if framework:
            query += " AND framework = %s"; params.append(framework)
        if tags:
            query += " AND tags && %s"; params.append(list(tags))

        with conn.cursor() as cur:
            cur.execute(query, params)
            rows = cur.fetchall()

        if not rows:
            return []

        q = q_emb.astype(np.float64).ravel()
        q_norm = np.linalg.norm(q) or 1.0
        q = q / q_norm

        scored: list[RagResult] = []
        for row in rows:
            emb_raw = row["embedding"]
            if emb_raw is None:
                continue
            emb = np.asarray(emb_raw, dtype=np.float64).ravel()
            e_norm = np.linalg.norm(emb) or 1.0
            sim = float(np.dot(q, emb / e_norm))
            if sim >= threshold:
                scored.append(
                    RagResult(
                        chunk=RagChunk(
                            id=row["id"], source=row["source"], framework=row["framework"],
                            kind=row.get("kind"), tags=row.get("tags") or [],
                            content=row["content"], metadata=row.get("metadata") or {},
                        ),
                        similarity=sim,
                    )
                )

        scored.sort(key=lambda x: x.similarity, reverse=True)
        return scored[:top_k]

    def _rows_to_results(self, rows) -> list[RagResult]:
        return [
            RagResult(
                chunk=RagChunk(
                    id=row["id"], source=row["source"], framework=row["framework"],
                    kind=row.get("kind"), tags=row.get("tags") or [],
                    content=row["content"], metadata=row.get("metadata") or {},
                ),
                similarity=float(row.get("similarity", 0.0)),
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
                query += " WHERE framework = %s"; params.append(framework)
            with conn.cursor() as cur:
                cur.execute(query, params)
                return int(cur.fetchone()["cnt"]) if cur.rowcount else 0
        except Exception:
            return 0

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
            return None
