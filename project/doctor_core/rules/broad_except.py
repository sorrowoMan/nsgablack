"""Broad exception swallow rule."""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Callable, List

from ..model import DoctorDiagnostic
from blackbase.project.doctor_scope import source_files


def _is_broad_exception_type(node: ast.AST | None) -> bool:
    if node is None:
        return True
    if isinstance(node, ast.Name):
        return node.id in {"Exception", "BaseException"}
    if isinstance(node, ast.Tuple):
        return any(_is_broad_exception_type(item) for item in node.elts)
    return False


def _returns_failure(value: ast.AST | None, exception_name: str | None) -> bool:
    """Recognize returned failure evidence, not just the presence of a return.

    This is deliberately local: a constant fallback remains a finding. A bound
    exception returned in a payload is observable by the caller. Explicit
    negative result envelopes may instead contain a fixed diagnostic message.
    """
    if value is None:
        return False
    if exception_name and any(isinstance(node, ast.Name) and node.id == exception_name
                              for node in ast.walk(value)):
        return True
    for node in ast.walk(value):
        if isinstance(node, ast.Dict):
            fields = {key.value: val for key, val in zip(node.keys, node.values)
                      if isinstance(key, ast.Constant) and isinstance(key.value, str)}
        elif isinstance(node, ast.Call):
            fields = {kw.arg: kw.value for kw in node.keywords if kw.arg}
        else:
            continue
        negative = any(isinstance(fields.get(key), ast.Constant) and fields[key].value is False
                       for key in ("ok", "is_valid", "applied"))
        diagnostic = any(isinstance(fields.get(key), ast.Constant)
                         and isinstance(fields[key].value, str) and fields[key].value.strip()
                         for key in ("error", "reason", "error_message"))
        if negative and diagnostic:
            return True
    return False


def _handler_body_is_swallow(body: List[ast.stmt], exception_name: str | None = None) -> bool:
    if not body:
        return False
    for stmt in body:
        if isinstance(stmt, (ast.Pass, ast.Continue, ast.Break)):
            continue
        if isinstance(stmt, ast.Return):
            if _returns_failure(stmt.value, exception_name):
                return False
            continue
        return False
    return True


def check_broad_exception_swallow(
    *,
    root: Path,
    diags: List[DoctorDiagnostic],
    strict: bool,
    add: Callable[[List[DoctorDiagnostic], str, str, str, Path | None], None],
) -> None:
    for py_file in source_files(root):
        if py_file.name.startswith("__"):
            continue
        if any(part in {".venv", "venv", "__pycache__", ".git"} for part in py_file.parts):
            continue
        try:
            tree = ast.parse(py_file.read_text(encoding="utf-8-sig"), filename=str(py_file))
        except (OSError, SyntaxError, UnicodeError) as exc:
            add(diags, "error" if strict else "warn", "source-parse-failed",
                f"Cannot read/parse source: {exc}", py_file,
                line=getattr(exc, "lineno", None), column=getattr(exc, "offset", None))
            continue
        try:
            rel = py_file.relative_to(root)
        except ValueError:
            rel = py_file
        is_core_path = len(rel.parts) > 0 and rel.parts[0] == "core"
        for node in ast.walk(tree):
            if not isinstance(node, ast.Try):
                continue
            for handler in node.handlers:
                if not _is_broad_exception_type(handler.type):
                    continue
                if not _handler_body_is_swallow(list(handler.body or []), handler.name):
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
                    line=line,
                    column=handler.col_offset + 1,
                )

