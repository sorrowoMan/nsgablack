from __future__ import annotations

from types import SimpleNamespace

import numpy as np
import pytest

from nsgablack.rag.config import RAG_STORAGE_DIMENSION, RagConfig, resolve_framework_root
from nsgablack.rag.embed import Embedder
from nsgablack.rag.indexer import _index_framework, _load_catalog
from nsgablack.rag.store import (
    RAG_STORE_SCHEMA,
    RagChunk,
    RagStore,
    _TABLE_SQL_NATIVE,
    _TABLE_SQL_VECTOR,
    _vector_literal,
)


class _Catalog:
    def list(self):
        return [
            {
                "key": "adapter.demo",
                "kind": "adapter",
                "import_path": "demo:DemoAdapter",
                "tags": ["demo"],
            }
        ]


class _Embedder:
    def __init__(self) -> None:
        self.config = SimpleNamespace(batch_size=1)
        self.calls: list[tuple[str, ...]] = []

    @property
    def space(self) -> str:
        return "test:embedding:3"

    def embed_batch(self, texts):
        values = tuple(str(value) for value in texts)
        self.calls.append(values)
        return np.ones((len(values), 3), dtype=np.float32)


class _Store:
    def __init__(self) -> None:
        self.inserts: list[tuple[tuple[object, ...], np.ndarray]] = []

    def insert_batch(self, chunks, embeddings, *, embedding_space):
        assert embedding_space == "test:embedding:3"
        self.inserts.append((tuple(chunks), np.asarray(embeddings).copy()))
        return len(chunks)


def test_catalog_loading_accepts_an_external_public_provider() -> None:
    profiles: list[str] = []

    entries = _load_catalog(
        "external_framework",
        "framework-core",
        loader=lambda profile: profiles.append(profile) or _Catalog(),
    )

    assert profiles == ["framework-core"]
    assert entries[0]["key"] == "adapter.demo"


def test_indexer_embeds_each_source_batch_once(tmp_path) -> None:
    (tmp_path / "demo.py").write_text(
        "class DemoAdapter:\n    pass\n",
        encoding="utf-8",
    )
    embedder = _Embedder()
    store = _Store()

    count = _index_framework(
        framework="external_framework",
        root=tmp_path,
        profile="framework-core",
        store=store,
        embedder=embedder,
        include_docs=False,
        catalog_loader=lambda profile: _Catalog(),
    )

    assert count > 0
    assert len(embedder.calls) == 1
    assert sum(len(chunks) for chunks, _ in store.inserts) == count
    assert all(np.all(embeddings == 1.0) for _, embeddings in store.inserts)


def test_framework_root_uses_explicit_environment_override(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("EXTERNAL_FRAMEWORK_ROOT", str(tmp_path))

    assert resolve_framework_root("external_framework") == tmp_path.resolve()


def test_local_embeddings_are_padded_into_the_configured_storage_dimension() -> None:
    class _LocalModel:
        def encode(self, texts, normalize_embeddings):
            assert normalize_embeddings is True
            return np.ones((len(texts), 384), dtype=np.float32)

    embedder = Embedder(local=True)
    embedder._local_model = _LocalModel()

    values = embedder.embed_batch(["first", "second"])

    assert values.shape == (2, embedder.config.embedding_dim)
    assert np.all(values[:, :384] == 1.0)
    assert np.all(values[:, 384:] == 0.0)
    assert embedder.space.endswith(f":{embedder.config.embedding_dim}")


def test_rag_config_rejects_a_dimension_that_cannot_fit_the_store_schema() -> None:
    with pytest.raises(ValueError, match="fixed embedding dimension"):
        RagConfig(embedding_dim=RAG_STORAGE_DIMENSION + 1)


def test_rag_uses_a_dedicated_postgres_url_not_the_catalog_backend(
    monkeypatch,
) -> None:
    monkeypatch.delenv("NSGABLACK_RAG_DB_URL", raising=False)
    monkeypatch.setenv("NSGABLACK_CATALOG_DB_URL", "mysql://catalog.example/db")

    assert RagConfig().pg_available is False

    with pytest.raises(ValueError, match="PostgreSQL URL scheme"):
        RagConfig(database_url="mysql://catalog.example/db")


def test_catalog_loading_failure_is_not_reinterpreted_as_an_empty_index() -> None:
    def broken_loader(profile):
        raise PermissionError(f"blocked profile: {profile}")

    with pytest.raises(RuntimeError, match="cannot load public Catalog"):
        _load_catalog(
            "external_framework",
            "framework-core",
            loader=broken_loader,
        )


def test_pgvector_values_use_a_typed_vector_literal() -> None:
    value = np.arange(RAG_STORAGE_DIMENSION, dtype=np.float32)

    literal = _vector_literal(value, dimension=RAG_STORAGE_DIMENSION)

    assert literal.startswith("[0,1,2,")
    assert literal.endswith("]")
    assert literal.count(",") == RAG_STORAGE_DIMENSION - 1


def test_embedding_space_is_part_of_the_store_primary_identity() -> None:
    assert RAG_STORE_SCHEMA == "nsgablack.rag.store.v2"
    assert "PRIMARY KEY (embedding_space, id)" in _TABLE_SQL_VECTOR
    assert "PRIMARY KEY (embedding_space, id)" in _TABLE_SQL_NATIVE

    class _Cursor:
        def __init__(self) -> None:
            self.calls = []

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

        def execute(self, query, params):
            self.calls.append((query, params))

    class _Connection:
        closed = False

        def __init__(self) -> None:
            self.cursor_instance = _Cursor()

        def cursor(self):
            return self.cursor_instance

        def commit(self):
            return None

    connection = _Connection()
    store = RagStore(RagConfig(database_url="postgresql://example/rag"))
    store._conn = connection
    store._has_vector = False
    chunk = RagChunk(
        id="framework.module:Demo",
        source="module.py",
        framework="framework",
        kind="adapter",
        tags=[],
        content="Demo",
    )
    embedding = np.ones((1, RAG_STORAGE_DIMENSION), dtype=np.float32)

    store.insert_batch([chunk], embedding, embedding_space="openai:model:512")
    store.insert_batch([chunk], embedding, embedding_space="local:model:512")

    assert len(connection.cursor_instance.calls) == 2
    for query, _ in connection.cursor_instance.calls:
        assert "ON CONFLICT (embedding_space, id)" in query
    spaces = [params[7] for _, params in connection.cursor_instance.calls]
    assert spaces == ["openai:model:512", "local:model:512"]


def test_store_health_never_reports_database_failure_as_an_empty_success() -> None:
    store = RagStore(RagConfig(database_url="postgresql://example/rag"))

    def denied_connection():
        raise PermissionError("denied")

    store._get_conn = denied_connection

    health = store.health()

    assert health.status == "error"
    assert health.current is False
    assert health.total_chunks == 0
    assert health.error_type == "PermissionError"


def test_store_count_does_not_collapse_unavailable_storage_to_zero() -> None:
    store = RagStore(RagConfig(database_url=None))

    with pytest.raises(RuntimeError, match="not configured"):
        store.chunk_count()


def test_store_detects_the_existing_embedding_column_type() -> None:
    class _Cursor:
        def __init__(self, column_type: str) -> None:
            self.column_type = column_type

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

        def execute(self, query):
            assert "pg_attribute" in query

        def fetchone(self):
            return {"column_type": self.column_type}

    class _Connection:
        def __init__(self, column_type: str) -> None:
            self.column_type = column_type

        def cursor(self):
            return _Cursor(self.column_type)

    assert RagStore._embedding_column_is_vector(_Connection("vector(512)")) is True
    assert RagStore._embedding_column_is_vector(_Connection("double precision[]")) is False
