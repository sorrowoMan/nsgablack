#!/usr/bin/env python
"""MCP server exposing RAG semantic search as tools for any MCP-compatible Agent."""

from __future__ import annotations

import json
import sys
from pathlib import Path

# Ensure nsgablack is importable
_HERE = Path(__file__).resolve().parent
_REPO = _HERE.parent.parent  # rag/ -> nsgablack/ -> repo root
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))


def _search(args: dict) -> str:
    from nsgablack.rag import search

    results = search(
        args["query"],
        kind=args.get("kind"),
        tags=args.get("tags"),
        framework=args.get("framework"),
        top_k=args.get("top_k", 5),
        threshold=args.get("threshold", 0.2),
        local_embed=True,
    )
    if not results:
        return "(no results)"

    lines = []
    for i, r in enumerate(results, 1):
        c = r.chunk
        lines.append(f"{i}. [{c.framework}] {c.id}  (sim={r.similarity:.2f})")
        lines.append(f"   kind={c.kind}  source={c.source}")
        lines.append(f"   {c.content[:300]}")
        lines.append("")
    return "\n".join(lines)


def _status(args: dict) -> str:
    from nsgablack.rag import RagStore

    store = RagStore()
    store.init_tables()
    total = store.chunk_count()
    nsga = store.chunk_count(framework="nsgablack")
    ml = store.chunk_count(framework="mlblack")
    ts = store.last_indexed_at() or "never"

    return (
        f"Total chunks: {total}\n"
        f"  nsgablack: {nsga}\n  mlblack: {ml}\n"
        f"Last indexed: {ts}"
    )


TOOLS = {
    "rag_search": {
        "description": "Semantic search over nsgablack + mlblack framework knowledge (source code, catalog entries, docs). Use this FIRST when exploring component capabilities, APIs, or architecture.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Natural language query"},
                "kind": {"type": "string", "description": "Filter by component kind (adapter, plugin, problem, bias, ...)"},
                "tags": {"type": "array", "items": {"type": "string"}, "description": "Filter by tags"},
                "framework": {"type": "string", "enum": ["nsgablack", "mlblack"], "description": "Limit to one framework"},
                "top_k": {"type": "integer", "default": 5, "description": "Max results"},
                "threshold": {"type": "number", "default": 0.2, "description": "Min cosine similarity 0-1"},
            },
            "required": ["query"],
        },
    },
    "rag_status": {
        "description": "Show RAG index status — chunk counts per framework, last indexed timestamp.",
        "inputSchema": {"type": "object", "properties": {}},
    },
}

HANDLERS = {
    "rag_search": _search,
    "rag_status": _status,
}


def main():
    import mcp.server.stdio
    import mcp.types as types
    from mcp.server.lowlevel import Server

    server = Server("nsgablack-rag")

    @server.list_tools()
    async def list_tools() -> list[types.Tool]:
        return [
            types.Tool(name=name, description=cfg["description"], inputSchema=cfg["inputSchema"])
            for name, cfg in TOOLS.items()
        ]

    @server.call_tool()
    async def call_tool(name: str, arguments: dict) -> list[types.TextContent]:
        handler = HANDLERS.get(name)
        if handler is None:
            raise ValueError(f"Unknown tool: {name}")
        result = handler(arguments)
        return [types.TextContent(type="text", text=result)]

    mcp.server.stdio.run(server)


if __name__ == "__main__":
    main()
