"""AST-based source chunker — splits Python modules by function/class boundaries."""

from __future__ import annotations

import ast
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

logger = logging.getLogger(__name__)


@dataclass
class Chunk:
    id: str
    name: str
    content: str
    source: str
    kind: str | None = None
    tags: list[str] = field(default_factory=list)
    lineno: int = 0
    metadata: dict = field(default_factory=dict)


def chunk_module(
    source: str,
    file_path: str,
    *,
    framework: str = "nsgablack",
    kind: str | None = None,
    tags: list[str] | None = None,
    extra_meta: dict | None = None,
) -> list[Chunk]:
    """Parse a Python module and yield chunks for every top-level function/class.

    Each chunk contains: the function/class name, its full source (including
    decorators and docstring), and the module-level docstring as a separate
    introductory chunk.
    """
    tree = _safe_parse(source, file_path)
    if tree is None:
        return []

    chunks: list[Chunk] = []
    source_name = Path(file_path).name

    # Module-level docstring as a context chunk
    mod_doc = ast.get_docstring(tree)
    if mod_doc:
        chunks.append(
            Chunk(
                id=f"{framework}.{file_path}:module",
                name=f"{source_name} (module)",
                content=_clean_docstring(mod_doc),
                source=file_path,
                kind=kind,
                tags=list(tags or []),
                lineno=0,
                metadata=dict(extra_meta or {}, chunk_type="module_docstring"),
            )
        )

    # Walk top-level definitions
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            chunk = _node_to_chunk(node, source, file_path, framework, kind, tags, extra_meta)
            if chunk:
                chunks.append(chunk)

    return chunks


def chunk_document(
    text: str,
    file_path: str,
    *,
    framework: str = "nsgablack",
    kind: str = "doc",
    tags: list[str] | None = None,
    extra_meta: dict | None = None,
) -> list[Chunk]:
    """Split a Markdown document by ## headings."""
    chunks: list[Chunk] = []
    source_name = Path(file_path).stem

    # Split on ## headings (h2)
    sections = re.split(r"\n(?=## )", text)
    for i, section in enumerate(sections):
        section = section.strip()
        if not section:
            continue
        # Extract heading for id
        heading_match = re.match(r"## (.+)", section)
        heading = heading_match.group(1).strip() if heading_match else f"section_{i}"
        slug = re.sub(r"[^a-z0-9]+", "_", heading.lower()).strip("_")

        chunks.append(
            Chunk(
                id=f"{framework}.{file_path}:{slug}",
                name=heading,
                content=section[:2000],  # cap at 2000 chars
                source=file_path,
                kind=kind,
                tags=list(tags or []),
                lineno=i,
                metadata=dict(extra_meta or {}, chunk_type="doc_section"),
            )
        )
    return chunks


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _safe_parse(source: str, file_path: str) -> ast.Module | None:
    try:
        return ast.parse(source)
    except SyntaxError as exc:
        logger.warning("AST parse failed for %s: %s", file_path, exc)
        return None


def _node_to_chunk(
    node: ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef,
    source: str,
    file_path: str,
    framework: str,
    kind: str | None,
    tags: list[str] | None,
    extra_meta: dict | None,
) -> Chunk | None:
    try:
        seg = ast.get_source_segment(source, node)
    except Exception:
        return None
    if not seg:
        return None

    node_type = "class" if isinstance(node, ast.ClassDef) else "function"
    chunk_id = f"{framework}.{file_path}:{node.name}"

    # Extract docstring for better embedding quality
    doc = ast.get_docstring(node)
    content = f"{node.name}\n{doc}" if doc else seg

    return Chunk(
        id=chunk_id,
        name=node.name,
        content=content[:1500],
        source=file_path,
        kind=kind,
        tags=list(tags or []),
        lineno=node.lineno,
        metadata=dict(
            extra_meta or {},
            chunk_type=node_type,
            decorators=[d.id for d in node.decorator_list if isinstance(d, ast.Name)] if hasattr(node, "decorator_list") else [],
        ),
    )


def _clean_docstring(doc: str) -> str:
    """Normalize a docstring for embedding."""
    doc = doc.strip()
    doc = re.sub(r"\n\s*\n", "\n", doc)  # collapse empty lines
    return doc[:1500]
