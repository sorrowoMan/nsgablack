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
import json
import re
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Iterable, Optional, Tuple


_KIND_LABELS = {
    "bias": "Bias",
    "adapter": "Adapter",
    "plugin": "Plugin",
    "representation": "Representation",
    "suite": "Suite",
    "tool": "Tool",
    "example": "Example",
    "doc": "Doc",
}

_DOCTOR_LINE_PATTERNS = (
    re.compile(r"@L(?P<line>\d+)"),
    re.compile(r"\bline\s+(?P<line>\d+)\b", re.IGNORECASE),
)
_DOCTOR_WATCH_EXTENSIONS = {".py", ".toml", ".md", ".json", ".yaml", ".yml", ".ini", ".cfg"}
_DOCTOR_WATCH_IGNORED_DIRS = {
    ".git",
    ".venv",
    "venv",
    "__pycache__",
    ".mypy_cache",
    ".pytest_cache",
    "runs",
    "artifacts",
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
    entries = c.list()
    if args.kind:
        kind_set = {str(k).strip().lower() for k in args.kind}
        entries = [e for e in entries if e.kind in kind_set]
    if args.tag:
        tag_set = {str(t).strip().lower() for t in args.tag}
        entries = [e for e in entries if tag_set.issubset({x.lower() for x in e.tags})]
    label = ",".join(args.kind) if args.kind else "ALL"
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


def _cmd_catalog_add(args: argparse.Namespace) -> int:
    from .catalog.quick_add import build_entry_payload, upsert_catalog_entry

    payload = build_entry_payload(
        key=args.key,
        title=args.title,
        kind=args.kind,
        import_path=args.import_path,
        summary=args.summary,
        tags=args.tags,
        companions=args.companions,
        use_when=args.use_when,
        minimal_wiring=args.minimal_wiring,
        required_companions=args.required_companions,
        config_keys=args.config_keys,
        example_entry=args.example_entry,
        context_requires=args.context_requires,
        context_provides=args.context_provides,
        context_mutates=args.context_mutates,
        context_cache=args.context_cache,
        context_notes=args.context_notes,
    )
    upsert_catalog_entry(Path(args.file), payload, replace=not bool(args.no_replace))
    print(f"catalog entry upserted: {payload['key']} -> {args.file}")
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


def _doctor_extract_line_column(message: str) -> tuple[int | None, int | None]:
    text = str(message or "")
    for pattern in _DOCTOR_LINE_PATTERNS:
        match = pattern.search(text)
        if match is None:
            continue
        try:
            return int(match.group("line")), 1
        except Exception:
            continue
    return None, None


def _doctor_severity(level: str) -> str:
    return {"error": "error", "warn": "warning", "info": "info"}.get(str(level).strip().lower(), "info")


def _doctor_report_payload(report) -> dict:
    diagnostics: list[dict] = []
    default_path = str(report.project_root)
    for diag in report.diagnostics:
        line, column = _doctor_extract_line_column(str(getattr(diag, "message", "")))
        diagnostics.append(
            {
                "level": str(getattr(diag, "level", "")),
                "severity": _doctor_severity(str(getattr(diag, "level", ""))),
                "code": str(getattr(diag, "code", "")),
                "message": str(getattr(diag, "message", "")),
                "path": str(getattr(diag, "path", "") or default_path),
                "line": int(line) if line is not None else None,
                "column": int(column) if column is not None else None,
            }
        )
    return {
        "project_root": str(report.project_root),
        "summary": {
            "errors": int(report.error_count),
            "warnings": int(report.warn_count),
            "infos": int(report.info_count),
        },
        "diagnostics": diagnostics,
    }


def _format_doctor_problem_lines(report) -> str:
    rows: list[str] = []
    default_path = str(report.project_root)
    for diag in report.diagnostics:
        path = str(getattr(diag, "path", "") or default_path)
        line, column = _doctor_extract_line_column(str(getattr(diag, "message", "")))
        row = (
            f"{path}:{int(line) if line is not None else 1}:{int(column) if column is not None else 1}: "
            f"{_doctor_severity(str(getattr(diag, 'level', '')))} "
            f"{str(getattr(diag, 'code', ''))}: "
            f"{str(getattr(diag, 'message', '')).replace(chr(10), ' ').strip()}"
        )
        rows.append(row)
    return "\n".join(rows)


def _doctor_exit_code(report, *, strict: bool) -> int:
    if int(report.error_count) > 0:
        return 2
    if bool(strict) and int(report.warn_count) > 0:
        return 1
    return 0


def _doctor_print_report(*, report, output_format: str, format_doctor_report) -> None:
    fmt = str(output_format).strip().lower()
    if fmt == "json":
        print(json.dumps(_doctor_report_payload(report), ensure_ascii=False, indent=2))
        return
    if fmt == "problem":
        print(_format_doctor_problem_lines(report))
        return
    print(format_doctor_report(report))


def _doctor_watch_signature(root: Path) -> tuple[tuple[str, int, int], ...]:
    entries: list[tuple[str, int, int]] = []
    for file_path in root.rglob("*"):
        if not file_path.is_file():
            continue
        if any(part in _DOCTOR_WATCH_IGNORED_DIRS for part in file_path.parts):
            continue
        if file_path.suffix.lower() not in _DOCTOR_WATCH_EXTENSIONS:
            continue
        try:
            stat = file_path.stat()
        except OSError:
            continue
        try:
            rel = file_path.relative_to(root).as_posix()
        except Exception:
            rel = str(file_path)
        entries.append((rel, int(stat.st_mtime_ns), int(stat.st_size)))
    entries.sort()
    return tuple(entries)


def _cmd_project_doctor(args: argparse.Namespace) -> int:
    from .project import format_doctor_report, run_project_doctor

    output_format = "json" if bool(getattr(args, "json", False)) else str(getattr(args, "format", "text"))
    output_format = output_format.strip().lower()
    if output_format not in {"text", "json", "problem"}:
        output_format = "text"

    def _run_once() -> tuple[object, int]:
        report = run_project_doctor(
            path=Path(args.path) if args.path else Path.cwd(),
            instantiate_solver=bool(args.build),
            strict=bool(args.strict),
        )
        _doctor_print_report(report=report, output_format=output_format, format_doctor_report=format_doctor_report)
        return report, _doctor_exit_code(report, strict=bool(args.strict))

    if not bool(getattr(args, "watch", False)):
        _, exit_code = _run_once()
        return exit_code

    interval = float(getattr(args, "watch_interval", 1.0) or 1.0)
    if interval < 0.2:
        interval = 0.2

    report, exit_code = _run_once()
    watch_root = Path(report.project_root)
    last_sig = _doctor_watch_signature(watch_root)
    print(f"[doctor-watch] started root={watch_root} interval={interval:g}s format={output_format}")
    print("[doctor-watch] cycle-done")

    try:
        while True:
            time.sleep(interval)
            current_sig = _doctor_watch_signature(watch_root)
            if current_sig == last_sig:
                continue
            last_sig = current_sig
            stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            print(f"[doctor-watch] cycle-start {stamp}")
            report, exit_code = _run_once()
            watch_root = Path(report.project_root)
            print("[doctor-watch] cycle-done")
    except KeyboardInterrupt:
        print("[doctor-watch] stopped")
        return 130


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
    entries = c.list()
    if args.kind:
        kind_set = {str(k).strip().lower() for k in args.kind}
        entries = [e for e in entries if e.kind in kind_set]
    if args.tag:
        tag_set = {str(t).strip().lower() for t in args.tag}
        entries = [e for e in entries if tag_set.issubset({x.lower() for x in e.tags})]
    label = ",".join(args.kind) if args.kind else "ALL"
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

    p_add = sub_cat.add_parser("add", help="Quick add/update a catalog entry in TOML")
    p_add.add_argument("--file", default="catalog/entries.toml", help="Target TOML file path")
    p_add.add_argument("--key", required=True, help="Entry key, e.g. bias.my_rule")
    p_add.add_argument("--title", required=True, help="Entry title")
    p_add.add_argument(
        "--kind",
        required=True,
        choices=("adapter", "bias", "plugin", "representation", "suite", "tool", "example", "doc"),
        help="Entry kind",
    )
    p_add.add_argument("--import-path", required=True, help="Import path, e.g. pkg.mod:Symbol")
    p_add.add_argument("--summary", required=True, help="One-line summary")
    p_add.add_argument("--tags", action="append", default=[], help="Tag(s), repeatable or comma-separated")
    p_add.add_argument(
        "--companions",
        action="append",
        default=[],
        help="Companion keys, repeatable or comma-separated",
    )
    p_add.add_argument("--use-when", action="append", default=[], help="Usage scenarios, repeatable")
    p_add.add_argument("--minimal-wiring", action="append", default=[], help="Minimal wiring lines, repeatable")
    p_add.add_argument(
        "--required-companions",
        action="append",
        default=[],
        help="Required companions, repeatable or comma-separated",
    )
    p_add.add_argument("--config-keys", action="append", default=[], help="Config keys, repeatable or comma-separated")
    p_add.add_argument("--example-entry", default="", help="Example entry, e.g. examples/demo.py:build_solver")
    p_add.add_argument("--context-requires", action="append", default=[], help="Context requires keys, repeatable")
    p_add.add_argument("--context-provides", action="append", default=[], help="Context provides keys, repeatable")
    p_add.add_argument("--context-mutates", action="append", default=[], help="Context mutates keys, repeatable")
    p_add.add_argument("--context-cache", action="append", default=[], help="Context cache keys, repeatable")
    p_add.add_argument("--context-notes", action="append", default=[], help="Context notes, repeatable")
    p_add.add_argument("--no-replace", action="store_true", help="Append instead of replacing existing key")
    p_add.set_defaults(func=_cmd_catalog_add)

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
        help="Call build_solver() to validate solver assembly and collect contracts",
    )
    p_doctor.add_argument(
        "--strict",
        action="store_true",
        help="Return non-zero when warnings exist",
    )
    p_doctor.add_argument(
        "--format",
        choices=("text", "json", "problem"),
        default="text",
        help="Output format for doctor report (default: text)",
    )
    p_doctor.add_argument(
        "--json",
        action="store_true",
        help="Shortcut for --format json",
    )
    p_doctor.add_argument(
        "--watch",
        action="store_true",
        help="Watch project files and re-run doctor when files change",
    )
    p_doctor.add_argument(
        "--watch-interval",
        type=float,
        default=1.0,
        help="Watch polling interval in seconds (default: 1.0)",
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
