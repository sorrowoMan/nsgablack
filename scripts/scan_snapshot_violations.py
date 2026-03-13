#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Context/Snapshot protocol violation scanner.

Usage:
    python -m nsgablack.scripts.scan_snapshot_violations [path] [--strict]

Scans all .py files under [path] and reports lines that:
  1. Write a large-object key directly into context (bypassing SnapshotStore)
  2. Read a large-object key from context without going through the _ref pattern

Large-object keys (must NEVER appear raw in context assignments):
  - "population"
  - "objectives"
  - "constraint_violations"
  - "history"
  - "pareto_solutions"
  - "pareto_objectives"
  - "decision_trace"

Correct pattern:  context[KEY_POPULATION_REF] = snapshot_key   (use _ref)
Violation:        context[KEY_POPULATION]     = population_array
"""

from __future__ import annotations

import ast
import sys
import textwrap
from pathlib import Path
from typing import List, NamedTuple

# ---------------------------------------------------------------------------
# Keys that represent large objects and must NOT be set directly in context
# ---------------------------------------------------------------------------
_LARGE_OBJECT_KEYS = {
    "population",
    "objectives",
    "constraint_violations",
    "history",
    "pareto_solutions",
    "pareto_objectives",
    "decision_trace",
}

# Corresponding safe *_ref keys
_REF_SUFFIX = "_ref"

# Variable names that represent context dicts (heuristic)
_CONTEXT_VAR_NAMES = {
    "context",
    "ctx",
    "context_store",
    "ctx_store",
    "build_context",
}


class Violation(NamedTuple):
    file: Path
    line: int
    col: int
    key: str
    kind: str   # "direct_write" | "direct_read"
    snippet: str


def _is_context_subscript_write(node: ast.Assign, large_keys: set) -> List[tuple]:
    """Detect context[LARGE_KEY] = value assignments."""
    violations = []
    for target in node.targets:
        if not isinstance(target, ast.Subscript):
            continue
        value_node = target.value
        if not isinstance(value_node, ast.Name):
            continue
        if value_node.id not in _CONTEXT_VAR_NAMES:
            continue
        # Get the subscript key
        slice_node = target.slice
        key_str = _extract_string_value(slice_node)
        if key_str and key_str in large_keys and not key_str.endswith(_REF_SUFFIX):
            violations.append((node.lineno, node.col_offset, key_str, "direct_write"))
    return violations


def _is_large_key_string(node: ast.expr) -> str | None:
    """Return string value if node is a large-object key constant."""
    val = _extract_string_value(node)
    if val and val in _LARGE_OBJECT_KEYS and not val.endswith(_REF_SUFFIX):
        return val
    return None


def _extract_string_value(node: ast.expr) -> str | None:
    """Extract string value from AST node (Constant or Attribute)."""
    if isinstance(node, ast.Constant) and isinstance(node.s, str):
        return node.s
    # Handle KEY_POPULATION style attribute access (NAME.attr)
    if isinstance(node, ast.Name):
        name = node.id
        # Map variable name pattern KEY_X -> "x"
        if name.startswith("KEY_"):
            return name[4:].lower()
    return None


def scan_file(path: Path, source_lines: List[str]) -> List[Violation]:
    """Scan a single Python file for snapshot protocol violations."""
    violations: List[Violation] = []
    try:
        tree = ast.parse("".join(source_lines), filename=str(path))
    except SyntaxError:
        return violations

    for node in ast.walk(tree):
        # Check direct writes: context["population"] = ...
        if isinstance(node, ast.Assign):
            for lineno, col, key, kind in _is_context_subscript_write(node, _LARGE_OBJECT_KEYS):
                snippet = source_lines[lineno - 1].rstrip() if lineno <= len(source_lines) else ""
                violations.append(Violation(path, lineno, col, key, kind, snippet))

        # Check direct reads: x = context["population"]  (without _ref)
        if isinstance(node, ast.Subscript):
            parent_candidates = _CONTEXT_VAR_NAMES
            if isinstance(node.value, ast.Name) and node.value.id in parent_candidates:
                key = _large_key_string = _is_large_key_string(node.slice)
                if key:
                    lineno = node.lineno
                    snippet = source_lines[lineno - 1].rstrip() if lineno <= len(source_lines) else ""
                    violations.append(
                        Violation(path, lineno, node.col_offset, key, "direct_read", snippet)
                    )

    return violations


def scan_directory(root: Path, exclude_dirs: set | None = None) -> List[Violation]:
    """Recursively scan all .py files under root."""
    if exclude_dirs is None:
        exclude_dirs = {
            "__pycache__", ".git", ".mypy_cache", ".pytest_cache",
            ".venv", "venv", "node_modules", "site-packages",
        }
    all_violations: List[Violation] = []
    for py_file in sorted(root.rglob("*.py")):
        if any(part in exclude_dirs for part in py_file.parts):
            continue
        try:
            source_lines = py_file.read_text(encoding="utf-8", errors="replace").splitlines(keepends=True)
        except OSError:
            continue
        all_violations.extend(scan_file(py_file, source_lines))
    return all_violations


def format_report(violations: List[Violation], root: Path) -> str:
    if not violations:
        return "✅ No context/snapshot protocol violations found.\n"

    lines = [
        f"⚠️  Found {len(violations)} context/snapshot protocol violation(s):\n",
        "━" * 72,
    ]
    by_file: dict[Path, List[Violation]] = {}
    for v in violations:
        by_file.setdefault(v.file, []).append(v)

    for file, file_violations in sorted(by_file.items()):
        try:
            rel = file.relative_to(root)
        except ValueError:
            rel = file
        lines.append(f"\n📄 {rel}")
        for v in file_violations:
            kind_label = "WRITE" if v.kind == "direct_write" else "READ "
            lines.append(
                f"  [{kind_label}] line {v.line:4d}  key='{v.key}'"
            )
            lines.append(f"         {v.snippet.strip()}")
            # Suggest fix
            ref_key = f"{v.key}_ref"
            if v.kind == "direct_write":
                lines.append(
                    f"         ↳ Fix: use SnapshotStore.write() and store "
                    f"context['{ref_key}'] = snapshot_key"
                )
            else:
                lines.append(
                    f"         ↳ Fix: read context['{ref_key}'] then "
                    f"SnapshotStore.read(snapshot_key)"
                )
    lines.append("\n" + "━" * 72)
    lines.append(
        "\nReference: utils/context/context_keys.py — use *_REF keys for large objects.\n"
    )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(
        description="Scan for Context/Snapshot protocol violations.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent(
            """\
            Examples:
              python -m nsgablack.scripts.scan_snapshot_violations .
              python -m nsgablack.scripts.scan_snapshot_violations adapters/ --strict
            """
        ),
    )
    parser.add_argument("path", nargs="?", default=".", help="Root directory to scan")
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit with code 1 if any violations found",
    )
    args = parser.parse_args(argv)

    root = Path(args.path).resolve()
    if not root.exists():
        print(f"Error: path does not exist: {root}", file=sys.stderr)
        return 2

    violations = scan_directory(root)
    print(format_report(violations, root))

    if args.strict and violations:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
