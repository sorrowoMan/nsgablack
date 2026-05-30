"""Semantic retriever — query → embed → pgvector cosine search → ranked results."""

from __future__ import annotations

from typing import List, Optional

from .config import RagConfig
from .embed import Embedder
from .store import RagResult, RagStore


def search(
    query: str,
    *,
    kind: str | None = None,
    tags: list[str] | None = None,
    framework: str | None = None,
    top_k: int = 5,
    threshold: float = 0.5,
    local_embed: bool = False,
    store: RagStore | None = None,
) -> list[RagResult]:
    """Semantic search across indexed chunks.

    Args:
        query: Natural language query string.
        kind: Filter by component kind (e.g. "adapter", "plugin", "problem").
        tags: Filter by tags (e.g. ["resource", "l0"]).
        framework: Limit to "nsgablack" or "mlblack".
        top_k: Max results to return.
        threshold: Minimum cosine similarity (0-1).
        local_embed: Use local embedding model.
        store: Optional pre-configured store.

    Returns:
        List of RagResult, ordered by similarity descending.
    """
    config = RagConfig()
    embedder = Embedder(config, local=local_embed)
    store = store or RagStore(config)

    embedding = embedder.embed(query)
    results = store.search(
        embedding,
        kind=kind,
        tags=tags,
        framework=framework,
        top_k=top_k,
        threshold=threshold,
    )
    return results


def format_results(results: list[RagResult]) -> str:
    """Format search results for CLI display."""
    if not results:
        return "(no results)"

    lines = []
    for i, r in enumerate(results, 1):
        c = r.chunk
        lines.append(
            f"{i}. [{c.framework}] {c.id}  ({r.similarity:.2f})"
        )
        lines.append(f"   kind={c.kind}  tags={c.tags}")
        # Truncate content for display
        content_preview = c.content[:200].replace("\n", " ")
        lines.append(f"   {content_preview}...")
        lines.append("")
    return "\n".join(lines)
