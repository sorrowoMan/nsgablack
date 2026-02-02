#!/usr/bin/env python
"""
Command line entrypoint for nsgablack.

This CLI intentionally stays small:
- `catalog`: discoverability (where is X?)

Usage:
  python -m nsgablack catalog search vns
  python -m nsgablack catalog list --kind adapter
  python -m nsgablack catalog show adapter.vns
"""

from __future__ import annotations

import argparse
import sys
from typing import Iterable, Optional


_KIND_LABELS = {
    "bias": "Bias",
    "adapter": "Adapter",
    "plugin": "Plugin",
    "representation": "Representation",
    "suite": "Suite",
    "tool": "Tool",
    "example": "Example",
}


def _ensure_utf8_io() -> None:
    for name in ("stdout", "stderr", "stdin"):
        stream = getattr(sys, name, None)
        if stream is None:
            continue
        try:
            if hasattr(stream, "reconfigure"):
                stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


def _kind_label(kind: str) -> str:
    k = str(kind).strip().lower()
    return _KIND_LABELS.get(k, k)


def _print_entries(
    entries: Iterable,
    *,
    show_import: bool = False,
    show_tags: bool = False,
    show_summary: bool = True,
) -> None:
    entries = list(entries)
    if not entries:
        print("(no matches)")
        return

    key_w = max(8, max(len(e.key) for e in entries))
    kind_w = max(10, max(len(_kind_label(e.kind)) for e in entries))

    header_cols = ["KEY".ljust(key_w), "KIND".ljust(kind_w), "TITLE"]
    if show_import:
        header_cols.append("IMPORT")
    print("  ".join(header_cols))
    print("-" * (sum(len(c) for c in header_cols) + 2 * (len(header_cols) - 1)))

    for e in entries:
        cols = [e.key.ljust(key_w), _kind_label(e.kind).ljust(kind_w), e.title]
        if show_import:
            cols.append(e.import_path)
        print("  ".join(cols))
        if show_tags and e.tags:
            print(" " * (key_w + 2) + f"tags: {', '.join(e.tags)}")
        if show_summary and e.summary:
            print(" " * (key_w + 2) + f"summary: {e.summary}")
        if e.companions:
            print(" " * (key_w + 2) + f"companions: {', '.join(e.companions)}")
        print()


def _cmd_catalog_search(args: argparse.Namespace) -> int:
    from .catalog import get_catalog

    c = get_catalog()
    entries = c.search(
        args.query,
        kinds=args.kind,
        tags=args.tag,
        limit=args.limit,
    )
    print(f"Catalog search: {args.query!r}  (hits={len(entries)})")
    _print_entries(
        entries,
        show_import=args.show_import,
        show_tags=args.show_tags,
        show_summary=not args.no_summary,
    )
    print("Hint: `python -m nsgablack catalog show <key>` for details/companions.")
    return 0


def _cmd_catalog_list(args: argparse.Namespace) -> int:
    from .catalog import get_catalog

    c = get_catalog()
    entries = c.list(kind=args.kind, tag=args.tag)
    label = args.kind if args.kind else "ALL"
    print(f"Catalog list: kind={label!r}  (count={len(entries)})")
    _print_entries(
        entries,
        show_import=args.show_import,
        show_tags=args.show_tags,
        show_summary=not args.no_summary,
    )
    print("Hint: `python -m nsgablack catalog show <key>` for details/companions.")
    return 0


def _cmd_catalog_show(args: argparse.Namespace) -> int:
    from .catalog import get_catalog

    c = get_catalog()
    e = c.get(args.key)
    if e is None:
        print(f"catalog: key not found: {args.key}", file=sys.stderr)
        return 2

    print(f"key: {e.key}")
    print(f"kind: {_kind_label(e.kind)}")
    print(f"title: {e.title}")
    print(f"import: {e.import_path}")
    if e.tags:
        print("tags:", ", ".join(e.tags))
    if e.summary:
        print("summary:", e.summary)
    if e.companions:
        print("companions:")
        for ck in e.companions:
            ce = c.get(ck)
            if ce is None:
                print(f"  - {ck} (missing)")
            else:
                print(f"  - {ce.key} ({ce.kind}) -> {ce.import_path}")
    return 0


def _cmd_run_inspector(args: argparse.Namespace) -> int:
    from .utils.viz import launch_from_entry

    return int(launch_from_entry(args.entry))


def _add_common_filters(p: argparse.ArgumentParser) -> None:
    p.add_argument(
        "--kind",
        action="append",
        default=None,
        help="Filter by kind (repeatable), e.g. --kind adapter --kind bias",
    )
    p.add_argument(
        "--tag",
        action="append",
        default=None,
        help="Filter by tag (repeatable), e.g. --tag vns --tag multiobjective",
    )
    p.add_argument("--show-import", action="store_true", help="Print import_path column")
    p.add_argument("--show-tags", action="store_true", help="Print tags")
    p.add_argument("--no-summary", action="store_true", help="Do not print summary/companions")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="nsgablack", add_help=True)
    sub = parser.add_subparsers(dest="command", required=True)

    # catalog
    p_cat = sub.add_parser("catalog", help="Discoverability registry (where is X?)")
    sub_cat = p_cat.add_subparsers(dest="catalog_cmd", required=True)

    p_search = sub_cat.add_parser("search", help="Search entries by keyword")
    p_search.add_argument("query", help="Search query (space separated tokens are AND)")
    _add_common_filters(p_search)
    p_search.add_argument("--limit", type=int, default=20, help="Max results (default: 20)")
    p_search.set_defaults(func=_cmd_catalog_search)

    p_list = sub_cat.add_parser("list", help="List entries")
    _add_common_filters(p_list)
    p_list.set_defaults(func=_cmd_catalog_list)

    p_show = sub_cat.add_parser("show", help="Show one entry details and companions")
    p_show.add_argument("key", help="Entry key, e.g. adapter.vns")
    p_show.set_defaults(func=_cmd_catalog_show)

    # run_inspector
    p_inspect = sub.add_parser("run_inspector", help="Launch Run Inspector (Tk UI)")
    p_inspect.add_argument("--entry", required=True, help="path/to/script.py:build_solver")
    p_inspect.set_defaults(func=_cmd_run_inspector)

    return parser


def main(argv: Optional[list[str]] = None) -> int:
    _ensure_utf8_io()
    parser = build_parser()
    args = parser.parse_args(argv)
    func = getattr(args, "func", None)
    if func is None:
        parser.print_help()
        return 2
    return int(func(args))


if __name__ == "__main__":
    raise SystemExit(main())
