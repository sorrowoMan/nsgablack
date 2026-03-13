"""Broad exception swallow rule."""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Callable, List

from ..model import DoctorDiagnostic


def _is_broad_exception_type(node: ast.AST | None) -> bool:
    if node is None:
        return True
    if isinstance(node, ast.Name):
        return node.id in {"Exception", "BaseException"}
    if isinstance(node, ast.Tuple):
        return any(_is_broad_exception_type(item) for item in node.elts)
    return False


def _handler_body_is_swallow(body: List[ast.stmt]) -> bool:
    if not body:
        return False
    for stmt in body:
        if isinstance(stmt, (ast.Pass, ast.Continue, ast.Break)):
            continue
        if isinstance(stmt, ast.Return):
            continue
        return False
    return True


def check_broad_exception_swallow(
    *,
    root: Path,
    diags: List[DoctorDiagnostic],
    strict: bool,
    add: Callable[[List[DoctorDiagnostic], str, str, str, Path | None], None],
    looks_like_scaffold_project: Callable[[Path], bool],
) -> None:
    if not looks_like_scaffold_project(root):
        add(
            diags,
            "info",
            "broad-except-skip",
            "Skip broad-exception swallow scan outside scaffold project roots.",
            root,
        )
        return

    for py_file in root.rglob("*.py"):
        if py_file.name.startswith("__"):
            continue
        if py_file.name in {"build_solver.py", "project_registry.py"}:
            continue
        if any(part in {".venv", "venv", "__pycache__", ".git"} for part in py_file.parts):
            continue
        try:
            tree = ast.parse(py_file.read_text(encoding="utf-8", errors="ignore"), filename=str(py_file))
        except Exception:
            continue
        try:
            rel = py_file.relative_to(root)
        except Exception:
            rel = py_file
        is_core_path = len(rel.parts) > 0 and rel.parts[0] == "core"
        for node in ast.walk(tree):
            if not isinstance(node, ast.Try):
                continue
            for handler in node.handlers:
                if not _is_broad_exception_type(handler.type):
                    continue
                if not _handler_body_is_swallow(list(handler.body or [])):
                    continue
                line = int(getattr(handler, "lineno", 0) or 0)
                code = "broad-except-swallow-core" if is_core_path else "broad-except-swallow"
                level = "error" if is_core_path or strict else "warn"
                add(
                    diags,
                    level,
                    code,
                    (
                        "Broad exception swallow detected (except Exception with pass/return/continue/break only). "
                        f"Replace with report_soft_error/logging or strict escalation at line {line}."
                    ),
                    py_file,
                )

