"""Dual-framework RAG indexer — catalog entries → source files → chunks → embeddings → PG."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

import numpy as np

from .chunker import Chunk, chunk_document, chunk_module
from .config import MLBLACK_ROOT, NSGABLACK_ROOT, RagConfig
from .embed import Embedder
from .store import RagChunk, RagStore

logger = logging.getLogger(__name__)


def build_index(
    *,
    frameworks: Sequence[str] = ("nsgablack", "mlblack"),
    profile: str = "framework-core",
    local_embed: bool = False,
    include_docs: bool = True,
    store: RagStore | None = None,
) -> dict[str, Any]:
    """Build (or refresh) the RAG index for one or both frameworks.

    Returns a summary dict with chunk counts per framework.
    """
    config = RagConfig()
    store = store or RagStore(config)
    embedder = Embedder(config, local=local_embed)

    store.init_tables()

    summary: dict[str, Any] = {}
    sources: list[tuple[str, str, Path]] = []  # (framework, kind, root)

    if "nsgablack" in frameworks:
        root = Path(NSGABLACK_ROOT)
        if root.is_dir():
            sources.append(("nsgablack", "module", root))
    if "mlblack" in frameworks:
        root = Path(MLBLACK_ROOT)
        if root.is_dir():
            sources.append(("mlblack", "module", root))

    for framework, _, root in sources:
        count = _index_framework(
            framework=framework,
            root=root,
            profile=profile,
            store=store,
            embedder=embedder,
            include_docs=include_docs,
        )
        summary[framework] = count

    return summary


def _index_framework(
    *,
    framework: str,
    root: Path,
    profile: str,
    store: RagStore,
    embedder: Embedder,
    include_docs: bool,
) -> int:
    logger.info("Indexing %s from %s (profile=%s)", framework, root, profile)

    catalog_entries = _load_catalog(framework, profile)
    total = 0

    # Group entries by import_path
    by_file: dict[str, list[dict]] = {}
    for e in catalog_entries:
        ip = e.get("import_path", "")
        if ip:
            # Convert "nsgablack.adapters.nsga2" -> "adapters/nsga2.py"
            # For mlblack: strip "mlblack." prefix since mlblack repo root IS the package
            module = ip.split(":")[0]
            parts = module.split(".")
            if framework == "mlblack" and parts[0] == "mlblack":
                parts = parts[1:]  # strip mlblack. prefix
            module_path = "/".join(parts) + ".py"
            by_file.setdefault(module_path, []).append(e)

    batch_chunks: list[RagChunk] = []

    for module_path, entries in by_file.items():
        full_path = root / module_path
        if not full_path.is_file():
            continue

        try:
            source = full_path.read_text(encoding="utf-8")
        except Exception as exc:
            logger.warning("Cannot read %s: %s", full_path, exc)
            continue

        # Common tags/kind from catalog entries
        kinds = list({e.get("kind", "") for e in entries if e.get("kind")})
        tags = _collect_tags(entries)
        primary_kind = kinds[0] if kinds else None

        chunks = chunk_module(
            source,
            str(module_path),
            framework=framework,
            kind=primary_kind,
            tags=tags,
            extra_meta={"catalog_keys": [e.get("key") for e in entries if e.get("key")]},
        )
        if not chunks:
            continue

        texts = [c.content for c in chunks]
        embeddings = embedder.embed_batch(texts)

        for c, emb in zip(chunks, embeddings):
            batch_chunks.append(
                RagChunk(
                    id=c.id,
                    source=c.source,
                    framework=framework,
                    kind=c.kind,
                    tags=c.tags,
                    content=c.content,
                    metadata=c.metadata,
                )
            )

        # Batch insert periodically
        if len(batch_chunks) >= embedder.config.batch_size * 5:
            store.insert_batch(batch_chunks, np.stack([np.zeros(embedder.dim)] * len(batch_chunks)))
            # Re-embed and insert properly
            store.insert_batch(batch_chunks, _collect_embeddings(batch_chunks, embedder))
            total += len(batch_chunks)
            logger.debug("Inserted %d chunks (total: %d)", len(batch_chunks), total)
            batch_chunks = []

    # Insert remaining
    if batch_chunks:
        emb_arrays = _collect_embeddings(batch_chunks, embedder)
        store.insert_batch(batch_chunks, emb_arrays)
        total += len(batch_chunks)

    # Index tutorial docs
    if include_docs:
        doc_count = _index_docs(root, framework, store, embedder)
        total += doc_count

    logger.info("%s: %d chunks indexed", framework, total)
    return total


def _index_docs(root: Path, framework: str, store: RagStore, embedder: Embedder) -> int:
    """Index Markdown tutorial docs."""
    docs_dir = root / "docs" / "standard_scaffold_tutorial"
    if not docs_dir.is_dir():
        return 0

    count = 0
    for md_path in sorted(docs_dir.glob("*.md")):
        try:
            text = md_path.read_text(encoding="utf-8")
        except Exception:
            continue

        rel = str(md_path.relative_to(root))
        chunks = chunk_document(text, rel, framework=framework)
        if not chunks:
            continue

        texts = [c.content for c in chunks]
        embeddings = embedder.embed_batch(texts)

        rag_chunks = [
            RagChunk(
                id=c.id,
                source=c.source,
                framework=framework,
                kind=c.kind,
                tags=c.tags,
                content=c.content,
                metadata=c.metadata,
            )
            for c in chunks
        ]
        store.insert_batch(rag_chunks, embeddings)
        count += len(chunks)

    if count:
        logger.info("%s docs: %d chunks indexed", framework, count)
    return count


def _load_catalog(framework: str, profile: str) -> list[dict]:
    """Load catalog entries for a framework."""
    import sys
    from pathlib import Path

    entries: list[dict] = []
    try:
        if framework == "nsgablack":
            from nsgablack.catalog import get_catalog
            cat = get_catalog()
        else:
            # Ensure mlblack is importable
            ml_root = Path(MLBLACK_ROOT)
            if str(ml_root.parent) not in sys.path:
                sys.path.insert(0, str(ml_root.parent))
            from mlblack.catalog import get_catalog as get_mlblack_catalog
            cat = get_mlblack_catalog()

        # Convert entries to dicts (handle both CatalogEntry objects and dicts)
        raw = []
        if hasattr(cat, '_entries'):
            raw = list(cat._entries)
        elif hasattr(cat, 'list_all'):
            raw = list(cat.list_all())

        for e in raw:
            if hasattr(e, 'to_dict'):
                entries.append(e.to_dict())
            elif isinstance(e, dict):
                entries.append(e)
            else:
                d = {}
                for attr in ('key', 'kind', 'title', 'import_path', 'tags', 'summary', 'companions'):
                    if hasattr(e, attr):
                        val = getattr(e, attr)
                        if attr == 'tags' and isinstance(val, (list, tuple)):
                            val = list(val)
                        d[attr] = val
                entries.append(d)
    except Exception as exc:
        logger.warning("Cannot load %s catalog: %s", framework, exc)

    # Filter by profile
    if profile == "framework-core":
        entries = [e for e in entries if "example" not in (e.get("tags") or []) and "doc" not in (e.get("tags") or [])]
    return entries


def _collect_tags(entries: list[dict]) -> list[str]:
    tags: set[str] = set()
    for e in entries:
        for t in e.get("tags") or []:
            if isinstance(t, str):
                tags.add(t)
    return sorted(tags)


def _collect_embeddings(chunks: list[RagChunk], embedder: Embedder) -> np.ndarray:
    """Embed a batch of RagChunks."""
    texts = [c.content for c in chunks]
    return embedder.embed_batch(texts)
