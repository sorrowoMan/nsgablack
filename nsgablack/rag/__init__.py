"""RAG (Retrieval-Augmented Generation) for nsgablack + mlblack.

Semantic search over framework components, source code, and documentation.
Built on PostgreSQL + pgvector with a dedicated operator-store URL.

Usage:
    from nsgablack.rag import build_index, search, format_results
    results = search("L0 dynamic resource allocation", kind="adapter")
    print(format_results(results))
"""

from .chunker import Chunk, chunk_document, chunk_module
from .config import RagConfig
from .embed import Embedder
from .indexer import build_index
from .retriever import format_results, search
from .store import RAG_STORE_SCHEMA, RagChunk, RagResult, RagStore, RagStoreHealth

__all__ = [
    "build_index",
    "search",
    "format_results",
    "RagConfig",
    "RagStore",
    "RagStoreHealth",
    "RAG_STORE_SCHEMA",
    "RagChunk",
    "RagResult",
    "Embedder",
    "Chunk",
    "chunk_module",
    "chunk_document",
]
