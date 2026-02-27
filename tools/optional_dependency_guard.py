#!/usr/bin/env python3
"""
Detect unsafe top-level imports of optional third-party dependencies.

Rule:
- If an optional dependency is imported at module top-level, it must be wrapped
  by a try/except block to avoid import-time crashes when the dependency is
  absent.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path
from typing import Iterable, List, Sequence, Tuple


OPTIONAL_DEPS = {
    # Existing optional extras / integrations
    "joblib",
    "matplotlib",
    "ray",
    "skopt",
    # Frequently optional integrations used in this repo
    "pandas",
    "networkx",
    "numba",
    "redis",
    "mysql",
    "pymysql",
    "cloudpickle",
    "opentelemetry",
    "torch",
    "tensorflow",
    "cupy",
}

TARGET_DIRS = (
    "bias",
    "catalog",
    "core",
    "plugins",
    "project",
    "representation",
    "utils",
)

SKIP_SUBSTRINGS = (
    "\\tests\\",
    "/tests/",
    "\\examples\\",
    "/examples/",
    "\\tools\\",
    "/tools/",
    "__pycache__",
)


def _iter_python_files(root: Path, target_dirs: Sequence[str]) -> Iterable[Path]:
    for rel in target_dirs:
        base = root / rel
        if not base.exists():
            continue
        for p in base.rglob("*.py"):
            s = str(p)
            if any(marker in s for marker in SKIP_SUBSTRINGS):
                continue
            yield p


def _imported_top_name(node: ast.AST) -> str | None:
    if isinstance(node, ast.Import):
        if not node.names:
            return None
        return node.names[0].name.split(".")[0]
    if isinstance(node, ast.ImportFrom):
        if not node.module:
            return None
        return node.module.split(".")[0]
    return None


def _collect_violations_in_block(
    body: Sequence[ast.stmt], in_try: bool, rel_path: str, out: List[Tuple[str, int, str]]
) -> None:
    for stmt in body:
        if isinstance(stmt, ast.Try):
            _collect_violations_in_block(stmt.body, True, rel_path, out)
            _collect_violations_in_block(stmt.handlers, in_try, rel_path, out)
            _collect_violations_in_block(stmt.orelse, in_try, rel_path, out)
            _collect_violations_in_block(stmt.finalbody, in_try, rel_path, out)
            continue

        dep = _imported_top_name(stmt)
        if dep and dep in OPTIONAL_DEPS and not in_try:
            out.append((rel_path, getattr(stmt, "lineno", 1), dep))

        nested_blocks: List[Sequence[ast.stmt]] = []
        if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            # Their internal imports are runtime-scoped; ignore for import-time safety.
            continue
        if isinstance(stmt, ast.If):
            nested_blocks.extend([stmt.body, stmt.orelse])
        elif isinstance(stmt, ast.With):
            nested_blocks.append(stmt.body)
        elif isinstance(stmt, ast.For):
            nested_blocks.extend([stmt.body, stmt.orelse])
        elif isinstance(stmt, ast.While):
            nested_blocks.extend([stmt.body, stmt.orelse])
        elif isinstance(stmt, ast.Match):
            for case in stmt.cases:
                nested_blocks.append(case.body)

        for nb in nested_blocks:
            _collect_violations_in_block(nb, in_try, rel_path, out)


def check_file(path: Path, repo_root: Path) -> List[Tuple[str, int, str]]:
    rel_path = str(path.relative_to(repo_root)).replace("\\", "/")
    try:
        source = path.read_text(encoding="utf-8-sig")
    except UnicodeDecodeError:
        source = path.read_text(encoding="utf-8-sig", errors="replace")
    tree = ast.parse(source, filename=rel_path)
    violations: List[Tuple[str, int, str]] = []
    _collect_violations_in_block(tree.body, False, rel_path, violations)
    return violations


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    violations: List[Tuple[str, int, str]] = []
    for py_file in _iter_python_files(root, TARGET_DIRS):
        violations.extend(check_file(py_file, root))

    print(f"optional_dep_guard_violations={len(violations)}")
    for rel_path, lineno, dep in sorted(violations):
        print(
            "[OPTIONAL-GUARD] "
            f"{rel_path}:{lineno}: top-level optional dependency '{dep}' import is not try-guarded"
        )

    return 1 if violations else 0


if __name__ == "__main__":
    raise SystemExit(main())
