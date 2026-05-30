"""RAG (Retrieval-Augmented Generation) for nsgablack + mlblack.

Semantic search over framework components, source code, and documentation.
Built on PostgreSQL + pgvector, reusing the catalog DB connection.

Usage:
    from nsgablack.rag import build_index, search, format_results
    results = search("L0 dynamic resource allocation", kind="adapter")
    print(format_results(results))
"""

from .chunker import Chunk, chunk_document, chunk_module
from .config import RagConfig
from .indexer import build_index
from .retriever import format_results, search
from .store import RagChunk, RagResult, RagStore

__all__ = [
    "build_index",
    "search",
    "format_results",
    "RagConfig",
    "RagStore",
    "RagChunk",
    "RagResult",
    "Chunk",
    "chunk_module",
    "chunk_document",
]
