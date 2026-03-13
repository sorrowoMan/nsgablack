"""Runtime private-call checks over broader non-contract source surfaces."""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Callable, Iterable, List, Sequence, Set

from ..model import DoctorDiagnostic
from .runtime_guards import check_runtime_private_calls


def _has_path_part(path: Path, names: Set[str]) -> bool:
    lowered = {part.lower() for part in path.parts}
    return bool(lowered & names)


def _is_python_test_file(path: Path) -> bool:
    name = path.name.lower()
    return name.startswith("test_") or name.endswith("_test.py")


def _is_skip_path(
    path: Path,
    *,
    skip_dir_names: Set[str],
    skip_tests: bool,
) -> bool:
    if _has_path_part(path, skip_dir_names):
        return True
    if not skip_tests:
        return False
    if _has_path_part(path, {"tests"}):
        return True
    return _is_python_test_file(path)


def _iter_runtime_surface_files(
    *,
    root: Path,
    file_patterns: Sequence[str],
    include_utils: bool,
    skip_dir_names: Set[str],
    skip_tests: bool,
) -> Iterable[Path]:
    seen: Set[Path] = set()

    for pattern in file_patterns:
        for candidate in root.rglob(pattern):
            if not candidate.is_file():
                continue
            if _is_skip_path(candidate, skip_dir_names=skip_dir_names, skip_tests=skip_tests):
                continue
            resolved = candidate.resolve()
            if resolved in seen:
                continue
            seen.add(resolved)
            yield candidate

    if not include_utils:
        return

    for utils_dir in root.rglob("utils"):
        if not utils_dir.is_dir():
            continue
        if _is_skip_path(utils_dir, skip_dir_names=skip_dir_names, skip_tests=skip_tests):
            continue
        for candidate in utils_dir.rglob("*.py"):
            if not candidate.is_file():
                continue
            if _is_skip_path(candidate, skip_dir_names=skip_dir_names, skip_tests=skip_tests):
                continue
            resolved = candidate.resolve()
            if resolved in seen:
                continue
            seen.add(resolved)
            yield candidate


def check_runtime_private_surface(
    *,
    root: Path,
    diags: List[DoctorDiagnostic],
    strict: bool,
    add: Callable[[List[DoctorDiagnostic], str, str, str, Path | None], None],
    file_patterns: Sequence[str],
    include_utils: bool,
    skip_dir_names: Set[str],
    skip_tests: bool,
) -> None:
    for py_file in _iter_runtime_surface_files(
        root=root,
        file_patterns=file_patterns,
        include_utils=bool(include_utils),
        skip_dir_names={name.lower() for name in skip_dir_names},
        skip_tests=bool(skip_tests),
    ):
        try:
            content = py_file.read_text(encoding="utf-8-sig")
            tree = ast.parse(content, filename=str(py_file))
        except Exception as exc:
            add(
                diags,
                "warn",
                "source-parse-failed",
                f"Cannot parse source file: {exc}",
                py_file,
            )
            continue

        check_runtime_private_calls(
            tree=tree,
            path=py_file,
            diags=diags,
            strict=bool(strict),
            add=add,
        )
