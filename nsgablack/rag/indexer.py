"""Optional framework-operator indexer over public Catalog surfaces."""

from __future__ import annotations

import logging
import inspect
from importlib import import_module
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

import numpy as np

from .chunker import Chunk, chunk_document, chunk_module
from .config import RagConfig, resolve_framework_root
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
    framework_roots: Mapping[str, Path | str] | None = None,
    catalog_loaders: Mapping[str, Callable[[str], Any]] | None = None,
) -> dict[str, Any]:
    """Build (or refresh) the RAG index for one or both frameworks.

    Returns a summary dict with chunk counts per framework.
    """
    config = RagConfig()
    store = store or RagStore(config)
    embedder = Embedder(config, local=local_embed)

    if not store.init_tables():
        raise RuntimeError("RAG store schema initialization failed")

    summary: dict[str, Any] = {}
    roots = dict(framework_roots or {})
    loaders = dict(catalog_loaders or {})
    sources: list[tuple[str, Path]] = []
    unresolved: list[str] = []
    for raw_name in frameworks:
        framework = str(raw_name or "").strip()
        if not framework or not framework.replace("_", "").isalnum():
            raise ValueError(f"invalid framework package name: {raw_name!r}")
        configured_root = roots.get(framework)
        root = (
            Path(configured_root).expanduser().resolve()
            if configured_root is not None
            else resolve_framework_root(framework)
        )
        if root is None or not root.is_dir():
            unresolved.append(framework)
            continue
        sources.append((framework, root))

    if unresolved:
        raise RuntimeError(
            "cannot resolve requested framework roots: " + ", ".join(unresolved)
        )

    for framework, root in sources:
        count = _index_framework(
            framework=framework,
            root=root,
            profile=profile,
            store=store,
            embedder=embedder,
            include_docs=include_docs,
            catalog_loader=loaders.get(framework),
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
    catalog_loader: Callable[[str], Any] | None,
) -> int:
    logger.info("Indexing %s from %s (profile=%s)", framework, root, profile)

    catalog_entries = _load_catalog(framework, profile, loader=catalog_loader)
    total = 0

    # Group entries by import_path
    by_file: dict[str, list[dict]] = {}
    for e in catalog_entries:
        ip = e.get("import_path", "")
        if ip:
            module = ip.split(":")[0]
            resolved = _resolve_module_path(module, root, framework)
            if resolved:
                by_file.setdefault(resolved, []).append(e)

    batch_chunks: list[RagChunk] = []
    batch_embeddings: list[np.ndarray] = []

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
            batch_embeddings.append(np.asarray(emb, dtype=np.float32))

        # Batch insert periodically
        if len(batch_chunks) >= embedder.config.batch_size * 5:
            store.insert_batch(
                batch_chunks,
                np.stack(batch_embeddings),
                embedding_space=embedder.space,
            )
            total += len(batch_chunks)
            logger.debug("Inserted %d chunks (total: %d)", len(batch_chunks), total)
            batch_chunks = []
            batch_embeddings = []

    # Insert remaining
    if batch_chunks:
        store.insert_batch(
            batch_chunks,
            np.stack(batch_embeddings),
            embedding_space=embedder.space,
        )
        total += len(batch_chunks)

    # Index tutorial docs
    if include_docs:
        doc_count = _index_docs(root, framework, store, embedder)
        total += doc_count

    logger.info("%s: %d chunks indexed", framework, total)
    return total


def _index_docs(root: Path, framework: str, store: RagStore, embedder: Embedder) -> int:
    """Index all Markdown docs under docs/ (recursively)."""
    docs_root = root / "docs"
    if not docs_root.is_dir():
        return 0

    count = 0
    for md_path in sorted(docs_root.rglob("*.md")):
        # Skip empty files and known non-doc paths
        if md_path.stat().st_size < 50:
            continue
        if ".git" in md_path.parts or "__pycache__" in md_path.parts:
            continue

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
        store.insert_batch(
            rag_chunks,
            embeddings,
            embedding_space=embedder.space,
        )
        count += len(chunks)

    if count:
        logger.info("%s docs: %d chunks indexed", framework, count)
    return count


def _load_catalog(
    framework: str,
    profile: str,
    *,
    loader: Callable[[str], Any] | None = None,
) -> list[dict]:
    """Load catalog entries for a framework."""
    entries: list[dict] = []
    try:
        if loader is not None:
            cat = loader(profile)
        else:
            catalog_module = import_module(f"{framework}.catalog")
            get_catalog = getattr(catalog_module, "get_catalog", None)
            if not callable(get_catalog):
                raise TypeError(f"{framework}.catalog does not expose get_catalog()")
            signature = inspect.signature(get_catalog)
            try:
                signature.bind(profile=profile)
            except TypeError:
                cat = get_catalog()
            else:
                cat = get_catalog(profile=profile)

        list_entries = getattr(cat, "list", None)
        if not callable(list_entries):
            raise TypeError(f"{framework} catalog does not expose public list()")
        raw = list(list_entries())

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
        raise RuntimeError(
            f"cannot load public Catalog for {framework}: {exc}"
        ) from exc

    # Filter by profile
    if profile == "framework-core":
        entries = [
            e
            for e in entries
            if str(e.get("kind", "")) not in {"example", "doc"}
            and "example" not in (e.get("tags") or [])
            and "doc" not in (e.get("tags") or [])
        ]
    if not entries:
        raise RuntimeError(
            f"public Catalog for {framework} returned no entries for profile {profile}"
        )
    return entries


def _resolve_module_path(module: str, root: Path, framework: str) -> str | None:
    """Resolve a dotted module name to a relative file path under root.

    Handles both regular modules (foo/bar.py) and packages (foo/bar/__init__.py).
    Uses importlib for the most reliable resolution.
    """
    # Try importlib first
    try:
        from importlib.util import find_spec

        spec = find_spec(module)
        if spec and spec.origin:
            origin = Path(spec.origin)
            try:
                return str(origin.relative_to(root))
            except ValueError:
                # origin is outside root — try path-based fallback
                pass
    except Exception:
        pass

    # Path-based fallback
    parts = module.split(".")
    if framework == "mlblack" and parts[0] == "mlblack":
        parts = parts[1:]
    elif framework == "nsgablack" and parts[0] == "nsgablack":
        parts = parts[1:]

    # Try foo/bar.py
    py_path = "/".join(parts) + ".py"
    if (root / py_path).is_file():
        return py_path

    # Try foo/bar/__init__.py (package)
    init_path = "/".join(parts) + "/__init__.py"
    if (root / init_path).is_file():
        return init_path

    return None


def _collect_tags(entries: list[dict]) -> list[str]:
    tags: set[str] = set()
    for e in entries:
        for t in e.get("tags") or []:
            if isinstance(t, str):
                tags.add(t)
    return sorted(tags)
