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
from pathlib import Path
from typing import Iterable, Optional, Tuple



def _safe_text(text: str) -> str:
    # Keep ASCII-only text for console safety; prefer the English part after " / ".
    if text is None:
        return ""
    if " / " in text:
        text = text.split(" / ", 1)[-1].strip()
    return "".join(ch for ch in text if ord(ch) < 128)



_KIND_LABELS = {
    "bias": "Bias",
    "adapter": "Adapter",
    "plugin": "Plugin",
    "representation": "Representation",
    "suite": "Suite",
    "tool": "Tool",
    "example": "Example",
}


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
            print(" " * (key_w + 2) + f"summary: {_safe_text(e.summary)}")
        if e.companions:
            print(" " * (key_w + 2) + f"companions: {', '.join(e.companions)}")
        print()


def _normalize_contract_values(values) -> Tuple[str, ...]:
    if isinstance(values, str):
        values = (values,)
    elif values is None:
        values = ()
    elif not isinstance(values, (list, tuple, set)):
        values = (str(values),)
    clean = tuple(str(v).strip() for v in values if str(v).strip())
    return clean


def _collect_contract_fields(obj, *, include_empty_declared: bool) -> list[Tuple[str, Tuple[str, ...]]]:
    out: list[Tuple[str, Tuple[str, ...]]] = []
    field_names = (
        "context_requires",
        "context_provides",
        "context_mutates",
        "context_cache",
        "context_notes",
    )
    for name in field_names:
        declared = hasattr(obj, name)
        clean = _normalize_contract_values(getattr(obj, name, ()))
        if clean:
            out.append((name, clean))
        elif include_empty_declared and declared:
            out.append((name, ("(empty)",)))
    return out


def _iter_contract_fields(e) -> Iterable[Tuple[str, Tuple[str, ...]]]:
    direct = _collect_contract_fields(e, include_empty_declared=False)
    if direct:
        for item in direct:
            yield item
        return

    # Fallback: infer from the referenced symbol when entry-level contracts are absent.
    if hasattr(e, "load"):
        try:
            symbol = e.load()
        except Exception:
            symbol = None
        if symbol is not None:
            for item in _collect_contract_fields(symbol, include_empty_declared=True):
                yield item
            return

    fields = (
        ("context_requires", getattr(e, "context_requires", ())),
        ("context_provides", getattr(e, "context_provides", ())),
        ("context_mutates", getattr(e, "context_mutates", ())),
        ("context_cache", getattr(e, "context_cache", ())),
        ("context_notes", getattr(e, "context_notes", ())),
    )
    for name, values in fields:
        clean = _normalize_contract_values(values)
        if clean:
            yield name, clean


def _print_contract_fields(e) -> None:
    has_contract = False
    for name, values in _iter_contract_fields(e):
        has_contract = True
        print(f"{name}:")
        for item in values:
            print(f"  - {item}")
    if not has_contract:
        print("context_contracts: (none)")


def _print_usage_fields(e) -> None:
    from .catalog import build_usage_profile

    usage = build_usage_profile(e)

    def _print_list(label: str, items: tuple[str, ...]) -> None:
        if not items:
            print(f"{label}: (none)")
            return
        print(f"{label}:")
        for item in items:
            print(f"  - {item}")

    _print_list("use_when", usage.use_when)
    _print_list("minimal_wiring", usage.minimal_wiring)
    _print_list("required_companions", usage.required_companions)
    _print_list("config_keys", usage.config_keys)
    print(f"example_entry: {usage.example_entry or '(none)'}")


def _cmd_catalog_search(args: argparse.Namespace) -> int:
    from .catalog import get_catalog

    c = get_catalog()
    entries = c.search(
        args.query,
        kinds=args.kind,
        tags=args.tag,
        fields=args.field,
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
    _print_usage_fields(e)
    _print_contract_fields(e)
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
    from .utils.viz import launch_empty, launch_from_entry

    if bool(args.empty):
        return int(launch_empty(workspace=args.workspace or None))
    if args.entry:
        return int(launch_from_entry(args.entry))
    return int(launch_empty(workspace=args.workspace or None))


def _cmd_project_init(args: argparse.Namespace) -> int:
    from .project import init_project

    root = init_project(Path(args.path), force=bool(args.force))
    print(f"Project created at: {root}")
    print("Next:")
    print(f"  cd {root}")
    print("  python -m nsgablack project doctor --path . --build")
    print("  python build_solver.py")
    return 0


def _cmd_project_doctor(args: argparse.Namespace) -> int:
    from .project import format_doctor_report, run_project_doctor

    report = run_project_doctor(
        path=Path(args.path) if args.path else Path.cwd(),
        instantiate_solver=bool(args.build),
    )
    print(format_doctor_report(report))
    if report.error_count > 0:
        return 2
    if bool(args.strict) and report.warn_count > 0:
        return 1
    return 0


def _cmd_project_catalog_search(args: argparse.Namespace) -> int:
    from .project.catalog import find_project_root, load_project_catalog

    root = find_project_root(Path(args.path) if args.path else Path.cwd())
    if root is None:
        print("project catalog: project_registry.py not found", file=sys.stderr)
        return 2
    c = load_project_catalog(root, include_global=bool(args.global_catalog))
    entries = c.search(
        args.query,
        kinds=args.kind,
        tags=args.tag,
        fields=args.field,
        limit=args.limit,
    )
    scope = "local+global" if args.global_catalog else "local"
    print(f"Project catalog search ({scope}): {args.query!r}  (hits={len(entries)})")
    _print_entries(
        entries,
        show_import=args.show_import,
        show_tags=args.show_tags,
        show_summary=not args.no_summary,
    )
    return 0


def _cmd_project_catalog_list(args: argparse.Namespace) -> int:
    from .project.catalog import find_project_root, load_project_catalog

    root = find_project_root(Path(args.path) if args.path else Path.cwd())
    if root is None:
        print("project catalog: project_registry.py not found", file=sys.stderr)
        return 2
    c = load_project_catalog(root, include_global=bool(args.global_catalog))
    entries = c.list(kind=args.kind, tag=args.tag)
    label = args.kind if args.kind else "ALL"
    scope = "local+global" if args.global_catalog else "local"
    print(f"Project catalog list ({scope}): kind={label!r}  (count={len(entries)})")
    _print_entries(
        entries,
        show_import=args.show_import,
        show_tags=args.show_tags,
        show_summary=not args.no_summary,
    )
    return 0


def _cmd_project_catalog_show(args: argparse.Namespace) -> int:
    from .project.catalog import find_project_root, load_project_catalog

    root = find_project_root(Path(args.path) if args.path else Path.cwd())
    if root is None:
        print("project catalog: project_registry.py not found", file=sys.stderr)
        return 2
    c = load_project_catalog(root, include_global=bool(args.global_catalog))
    e = c.get(args.key)
    if e is None:
        print(f"project catalog: key not found: {args.key}", file=sys.stderr)
        return 2
    print(f"key: {e.key}")
    print(f"kind: {_kind_label(e.kind)}")
    print(f"title: {e.title}")
    print(f"import: {e.import_path}")
    if e.tags:
        print("tags:", ", ".join(e.tags))
    if e.summary:
        print("summary:", e.summary)
    _print_usage_fields(e)
    _print_contract_fields(e)
    if e.companions:
        print("companions:", ", ".join(e.companions))
    return 0


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
    p_search.add_argument(
        "--field",
        choices=("all", "name", "tag", "context", "usage"),
        default="all",
        help="Match scope: all fields, name (key/title), tag, context contracts, or usage hints",
    )
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
    p_inspect.add_argument("--entry", default="", help="path/to/script.py:build_solver")
    p_inspect.add_argument("--workspace", default="", help="Workspace root for empty mode/catalog")
    p_inspect.add_argument("--empty", action="store_true", help="Start UI without preloaded entry")
    p_inspect.set_defaults(func=_cmd_run_inspector)

    # project
    p_project = sub.add_parser("project", help="Project scaffold & local catalog")
    sub_project = p_project.add_subparsers(dest="project_cmd", required=True)

    p_init = sub_project.add_parser("init", help="Create a local project scaffold")
    p_init.add_argument("path", help="Target directory for the project")
    p_init.add_argument("--force", action="store_true", help="Overwrite existing template files")
    p_init.set_defaults(func=_cmd_project_init)

    p_doctor = sub_project.add_parser("doctor", help="Check project structure, imports, and contracts")
    p_doctor.add_argument("--path", type=str, default=None, help="Project root (defaults to cwd)")
    p_doctor.add_argument(
        "--build",
        action="store_true",
        help="Call build_solver() to validate assembly and collect contracts",
    )
    p_doctor.add_argument(
        "--strict",
        action="store_true",
        help="Return non-zero when warnings exist",
    )
    p_doctor.set_defaults(func=_cmd_project_doctor)

    p_proj_cat = sub_project.add_parser("catalog", help="Project-local catalog tools")
    sub_proj_cat = p_proj_cat.add_subparsers(dest="project_catalog_cmd", required=True)

    p_proj_search = sub_proj_cat.add_parser("search", help="Search local project catalog")
    p_proj_search.add_argument("query", help="Search query")
    _add_common_filters(p_proj_search)
    p_proj_search.add_argument(
        "--field",
        choices=("all", "name", "tag", "context", "usage"),
        default="all",
        help="Match scope: all fields, name (key/title), tag, context contracts, or usage hints",
    )
    p_proj_search.add_argument("--limit", type=int, default=20, help="Max results (default: 20)")
    p_proj_search.add_argument("--path", type=str, default=None, help="Project root (defaults to cwd)")
    p_proj_search.add_argument("--global", dest="global_catalog", action="store_true", help="Include global catalog")
    p_proj_search.set_defaults(func=_cmd_project_catalog_search)

    p_proj_list = sub_proj_cat.add_parser("list", help="List local project catalog")
    _add_common_filters(p_proj_list)
    p_proj_list.add_argument("--path", type=str, default=None, help="Project root (defaults to cwd)")
    p_proj_list.add_argument("--global", dest="global_catalog", action="store_true", help="Include global catalog")
    p_proj_list.set_defaults(func=_cmd_project_catalog_list)

    p_proj_show = sub_proj_cat.add_parser("show", help="Show one project catalog entry")
    p_proj_show.add_argument("key", help="Entry key, e.g. project.bias.example")
    p_proj_show.add_argument("--path", type=str, default=None, help="Project root (defaults to cwd)")
    p_proj_show.add_argument("--global", dest="global_catalog", action="store_true", help="Include global catalog")
    p_proj_show.set_defaults(func=_cmd_project_catalog_show)

    return parser


def main(argv: Optional[list[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    func = getattr(args, "func", None)
    if func is None:
        parser.print_help()
        return 2
    return int(func(args))


if __name__ == "__main__":
    raise SystemExit(main())
