"""PostgreSQL chunk store — pgvector preferred, native PG array fallback."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from types import MappingProxyType
from typing import Any, Mapping, Sequence

import numpy as np

from .config import RagConfig

logger = logging.getLogger(__name__)
RAG_STORE_SCHEMA = "nsgablack.rag.store.v2"


def _embedding_array(value: np.ndarray, *, dimension: int) -> np.ndarray:
    array = np.asarray(value, dtype=np.float32).reshape(-1)
    if array.size != int(dimension):
        raise ValueError(
            f"embedding dimension mismatch: {array.size} vs {int(dimension)}"
        )
    if not np.all(np.isfinite(array)):
        raise ValueError("embedding values must be finite")
    return array


def _vector_literal(value: np.ndarray, *, dimension: int) -> str:
    array = _embedding_array(value, dimension=dimension)
    return "[" + ",".join(format(float(item), ".9g") for item in array) + "]"

_TABLE_SQL_VECTOR = """
CREATE TABLE IF NOT EXISTS rag_chunks (
    id          TEXT NOT NULL,
    source      TEXT NOT NULL,
    framework   TEXT NOT NULL,
    kind        TEXT,
    tags        TEXT[],
    content     TEXT NOT NULL,
    embedding   vector(512),
    embedding_space TEXT NOT NULL DEFAULT 'legacy',
    metadata    JSONB DEFAULT '{}'::jsonb,
    indexed_at  TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (embedding_space, id)
);
CREATE INDEX IF NOT EXISTS rag_chunks_fwk_idx ON rag_chunks(framework);
CREATE INDEX IF NOT EXISTS rag_chunks_kind_idx ON rag_chunks(kind);
CREATE INDEX IF NOT EXISTS rag_chunks_space_idx ON rag_chunks(embedding_space);
"""

_TABLE_SQL_NATIVE = """
CREATE TABLE IF NOT EXISTS rag_chunks (
    id          TEXT NOT NULL,
    source      TEXT NOT NULL,
    framework   TEXT NOT NULL,
    kind        TEXT,
    tags        TEXT[],
    content     TEXT NOT NULL,
    embedding   double precision[],
    embedding_space TEXT NOT NULL DEFAULT 'legacy',
    metadata    JSONB DEFAULT '{}'::jsonb,
    indexed_at  TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (embedding_space, id)
);
CREATE INDEX IF NOT EXISTS rag_chunks_fwk_idx ON rag_chunks(framework);
CREATE INDEX IF NOT EXISTS rag_chunks_kind_idx ON rag_chunks(kind);
CREATE INDEX IF NOT EXISTS rag_chunks_space_idx ON rag_chunks(embedding_space);
"""

_PRIMARY_KEY_V2_SQL = """
DO $$
DECLARE
    current_primary_key TEXT;
BEGIN
    SELECT constraint_row.conname
      INTO current_primary_key
      FROM pg_constraint AS constraint_row
     WHERE constraint_row.conrelid = 'rag_chunks'::regclass
       AND constraint_row.contype = 'p'
       AND pg_get_constraintdef(constraint_row.oid)
           <> 'PRIMARY KEY (embedding_space, id)'
     LIMIT 1;

    IF current_primary_key IS NOT NULL THEN
        EXECUTE format(
            'ALTER TABLE rag_chunks DROP CONSTRAINT %I',
            current_primary_key
        );
    END IF;

    IF NOT EXISTS (
        SELECT 1
          FROM pg_constraint AS constraint_row
         WHERE constraint_row.conrelid = 'rag_chunks'::regclass
           AND constraint_row.contype = 'p'
           AND pg_get_constraintdef(constraint_row.oid)
               = 'PRIMARY KEY (embedding_space, id)'
    ) THEN
        ALTER TABLE rag_chunks
            ADD CONSTRAINT rag_chunks_pkey PRIMARY KEY (embedding_space, id);
    END IF;
END
$$;
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


@dataclass(frozen=True)
class RagStoreHealth:
    """Bounded, explicit health evidence for the optional RAG store."""

    status: str
    schema: str = RAG_STORE_SCHEMA
    total_chunks: int = 0
    framework_counts: Mapping[str, int] = field(default_factory=dict)
    embedding_space_counts: Mapping[str, int] = field(default_factory=dict)
    last_indexed_at: str | None = None
    error_type: str | None = None
    error_message: str | None = None

    def __post_init__(self) -> None:
        if self.schema != RAG_STORE_SCHEMA:
            raise ValueError("unsupported RAG store schema")
        if self.status not in {"ok", "unavailable", "error"}:
            raise ValueError("invalid RAG store health status")
        if int(self.total_chunks) < 0:
            raise ValueError("RAG store health count must be non-negative")
        if self.status == "ok" and (self.error_type or self.error_message):
            raise ValueError("healthy RAG store cannot include an error")
        if self.status == "error" and not self.error_type:
            raise ValueError("failed RAG store health requires error_type")
        object.__setattr__(self, "total_chunks", int(self.total_chunks))
        object.__setattr__(
            self,
            "framework_counts",
            MappingProxyType(
                {
                    str(key): int(value)
                    for key, value in self.framework_counts.items()
                }
            ),
        )
        object.__setattr__(
            self,
            "embedding_space_counts",
            MappingProxyType(
                {
                    str(key): int(value)
                    for key, value in self.embedding_space_counts.items()
                }
            ),
        )
        if self.error_message is not None:
            object.__setattr__(self, "error_message", str(self.error_message)[:512])

    @property
    def current(self) -> bool:
        return self.status == "ok"

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "status": self.status,
            "current": self.current,
            "total_chunks": self.total_chunks,
            "framework_counts": dict(self.framework_counts),
            "embedding_space_counts": dict(self.embedding_space_counts),
            "last_indexed_at": self.last_indexed_at,
            "error_type": self.error_type,
            "error_message": self.error_message,
        }


class RagStore:
    """PostgreSQL store for RAG chunks.

    Uses pgvector extension if available (HNSW index, fast ANN).
    Falls back to native PG double precision[] with Python cosine similarity.
    """

    def __init__(self, config: RagConfig | None = None):
        self.config = config or RagConfig()
        self._conn = None
        self._has_vector = False  # set by init_tables()
        self._last_init_error: Exception | None = None

    # ------------------------------------------------------------------
    # Connection
    # ------------------------------------------------------------------

    def _get_conn(self):
        if self._conn is None or self._conn.closed:
            from psycopg import connect
            from psycopg.rows import dict_row

            if not self.config.pg_available:
                raise RuntimeError(
                    "RAG PostgreSQL store is not configured; set NSGABLACK_RAG_DB_URL"
                )
            url = str(self.config.pg_url or "")
            if url.startswith("postgresql+psycopg://"):
                url = url.replace(
                    "postgresql+psycopg://", "postgresql://", 1
                )
            self._conn = connect(url, row_factory=dict_row)
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
        self._last_init_error = None
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

        sql = _TABLE_SQL_VECTOR if has_vector else _TABLE_SQL_NATIVE

        try:
            with conn.cursor() as cur:
                cur.execute(sql)
                cur.execute(
                    "ALTER TABLE rag_chunks ADD COLUMN IF NOT EXISTS "
                    "embedding_space TEXT NOT NULL DEFAULT 'legacy'"
                )
                cur.execute(_PRIMARY_KEY_V2_SQL)
            conn.commit()
            self._has_vector = self._embedding_column_is_vector(conn)
            if self._has_vector:
                self._try_hnsw_index()
            return True
        except Exception as exc:
            conn.rollback()
            self._last_init_error = exc
            logger.warning("init_tables failed: %s", exc)
            return False

    @staticmethod
    def _embedding_column_is_vector(conn) -> bool:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT format_type(attribute.atttypid, attribute.atttypmod) AS column_type
                FROM pg_attribute AS attribute
                JOIN pg_class AS relation ON relation.oid = attribute.attrelid
                WHERE relation.relname = 'rag_chunks'
                  AND pg_table_is_visible(relation.oid)
                  AND attribute.attname = 'embedding'
                  AND attribute.attnum > 0
                  AND NOT attribute.attisdropped
                """
            )
            row = cur.fetchone()
        if not row:
            raise RuntimeError("rag_chunks.embedding column was not created")
        value = row.get("column_type") if isinstance(row, dict) else row[0]
        return str(value or "").lower().startswith("vector")

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
        *,
        embedding_space: str,
    ) -> int:
        if len(chunks) == 0:
            return 0
        if len(chunks) != len(embeddings):
            raise ValueError(
                f"chunks/embeddings length mismatch: {len(chunks)} vs {len(embeddings)}"
            )
        space = str(embedding_space or "").strip()
        if not space:
            raise ValueError("embedding_space must be non-empty")
        normalized_embeddings = tuple(
            _embedding_array(value, dimension=self.config.embedding_dim)
            for value in embeddings
        )

        conn = self._get_conn()
        now = datetime.now(timezone.utc).isoformat()
        count = 0

        with conn.cursor() as cur:
            for chunk, emb in zip(chunks, normalized_embeddings):
                if self._has_vector:
                    cur.execute(
                        """
                        INSERT INTO rag_chunks (id, source, framework, kind, tags, content, embedding, embedding_space, metadata, indexed_at)
                        VALUES (%s, %s, %s, %s, %s, %s, %s::vector, %s, %s, %s)
                        ON CONFLICT (embedding_space, id) DO UPDATE SET
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
                            _vector_literal(emb, dimension=self.config.embedding_dim),
                            space,
                            json.dumps(chunk.metadata or {}, ensure_ascii=False),
                            now,
                        ),
                    )
                else:
                    cur.execute(
                        """
                        INSERT INTO rag_chunks (id, source, framework, kind, tags, content, embedding, embedding_space, metadata, indexed_at)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (embedding_space, id) DO UPDATE SET
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
                            space,
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
        embedding_space: str,
    ) -> list[RagResult]:
        conn = self._get_conn()
        space = str(embedding_space or "").strip()
        if not space:
            raise ValueError("embedding_space must be non-empty")
        query_embedding = _embedding_array(
            query_embedding,
            dimension=self.config.embedding_dim,
        )

        if self._has_vector:
            return self._search_pgvector(
                conn, query_embedding, kind, tags, framework, top_k, threshold, space
            )
        return self._search_native(
            conn, query_embedding, kind, tags, framework, top_k, threshold, space
        )

    def _search_pgvector(
        self, conn, q_emb, kind, tags, framework, top_k, threshold, embedding_space
    ) -> list[RagResult]:
        emb_value = _vector_literal(q_emb, dimension=self.config.embedding_dim)
        query = """
            SELECT id, source, framework, kind, tags, content, metadata,
                   1 - (embedding <=> %s::vector) AS similarity
            FROM rag_chunks
            WHERE embedding IS NOT NULL
              AND embedding_space = %s
              AND 1 - (embedding <=> %s::vector) >= %s
        """
        params: list[Any] = [emb_value, embedding_space, emb_value, float(threshold)]
        if kind:
            query += " AND kind = %s"; params.append(kind)
        if framework:
            query += " AND framework = %s"; params.append(framework)
        if tags:
            query += " AND tags && %s"; params.append(list(tags))
        query += " ORDER BY embedding <=> %s::vector LIMIT %s"
        params.extend([emb_value, int(top_k)])

        with conn.cursor() as cur:
            cur.execute(query, params)
            rows = cur.fetchall()
        return self._rows_to_results(rows)

    def _search_native(
        self, conn, q_emb, kind, tags, framework, top_k, threshold, embedding_space
    ) -> list[RagResult]:
        """Python cosine similarity. Load matching rows, compare in memory."""
        query = """
            SELECT id, source, framework, kind, tags, content, embedding, metadata
            FROM rag_chunks
            WHERE embedding IS NOT NULL
              AND embedding_space = %s
        """
        params: list[Any] = [embedding_space]
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
            raise RuntimeError("RAG PostgreSQL store is not configured")
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

    def last_indexed_at(self) -> str | None:
        if not self.config.pg_available:
            raise RuntimeError("RAG PostgreSQL store is not configured")
        conn = self._get_conn()
        with conn.cursor() as cur:
            cur.execute("SELECT MAX(indexed_at) AS ts FROM rag_chunks")
            row = cur.fetchone()
        return str(row["ts"]) if row and row["ts"] else None

    def health(self) -> RagStoreHealth:
        """Return read-only store health; failures are never empty data."""

        if not self.config.pg_available:
            return RagStoreHealth(status="unavailable")
        try:
            conn = self._get_conn()
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT framework, COUNT(*) AS cnt "
                    "FROM rag_chunks GROUP BY framework"
                )
                framework_counts = {
                    str(row["framework"]): int(row["cnt"])
                    for row in cur.fetchall()
                }
                cur.execute(
                    "SELECT embedding_space, COUNT(*) AS cnt "
                    "FROM rag_chunks GROUP BY embedding_space"
                )
                embedding_space_counts = {
                    str(row["embedding_space"]): int(row["cnt"])
                    for row in cur.fetchall()
                }
                cur.execute("SELECT MAX(indexed_at) AS ts FROM rag_chunks")
                row = cur.fetchone()
            return RagStoreHealth(
                status="ok",
                total_chunks=sum(framework_counts.values()),
                framework_counts=framework_counts,
                embedding_space_counts=embedding_space_counts,
                last_indexed_at=(
                    str(row["ts"])
                    if row and row.get("ts") is not None
                    else None
                ),
            )
        except Exception as exc:
            return RagStoreHealth(
                status="error",
                error_type=type(exc).__name__,
                error_message=str(exc),
            )
