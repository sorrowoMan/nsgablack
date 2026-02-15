# -*- coding: utf-8 -*-
"""Project doctor checks for local scaffold projects."""

from __future__ import annotations

import ast
import importlib
import importlib.util
import inspect
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Sequence

from .catalog import find_project_root, load_project_entries


@dataclass(frozen=True)
class DoctorDiagnostic:
    level: str  # info / warn / error
    code: str
    message: str
    path: str | None = None


@dataclass(frozen=True)
class DoctorReport:
    project_root: Path
    diagnostics: Sequence[DoctorDiagnostic]

    @property
    def error_count(self) -> int:
        return sum(1 for d in self.diagnostics if d.level == "error")

    @property
    def warn_count(self) -> int:
        return sum(1 for d in self.diagnostics if d.level == "warn")

    @property
    def info_count(self) -> int:
        return sum(1 for d in self.diagnostics if d.level == "info")


_REQUIRED_DIRS = ("problem", "pipeline", "bias", "adapter", "plugins")
_REQUIRED_FILES = ("README.md", "build_solver.py", "project_registry.py")
_CONTRACT_KEYS = {"context_requires", "context_provides", "context_mutates", "context_cache", "context_notes"}
_USAGE_KEYS = {"use_when", "minimal_wiring", "required_companions", "config_keys", "example_entry"}
_CONTEXT_ENTRY_KEYS = {"context_requires", "context_provides", "context_mutates", "context_cache", "context_notes"}
_CONTRACT_CHECK_DIRS = ("pipeline", "bias", "adapter", "plugins")


def _add(diags: List[DoctorDiagnostic], level: str, code: str, msg: str, path: Path | None = None) -> None:
    diags.append(
        DoctorDiagnostic(
            level=level,
            code=code,
            message=msg,
            path=str(path) if path is not None else None,
        )
    )


def _load_module_from_file(module_name: str, file_path: Path):
    spec = importlib.util.spec_from_file_location(module_name, file_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot import module from file: {file_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # type: ignore[call-arg]
    return module


def _resolve_import_path(import_path: str):
    module_path, sep, attr_path = str(import_path).partition(":")
    if not module_path or not sep or not attr_path:
        raise ValueError(f"Invalid import_path: {import_path!r} (expected 'module:attr')")
    module = importlib.import_module(module_path)
    obj = module
    for part in attr_path.split("."):
        obj = getattr(obj, part)
    return obj


def _check_structure(root: Path, diags: List[DoctorDiagnostic]) -> None:
    for name in _REQUIRED_DIRS:
        folder = root / name
        if not folder.is_dir():
            _add(diags, "error", "missing-dir", f"Missing required directory: {name}", folder)
        elif not (folder / "README.md").is_file():
            _add(diags, "warn", "missing-folder-readme", f"Recommended: add {name}/README.md", folder / "README.md")

    for name in _REQUIRED_FILES:
        file_path = root / name
        if not file_path.is_file():
            _add(diags, "error", "missing-file", f"Missing required file: {name}", file_path)

    if not (root / "START_HERE.md").is_file():
        _add(diags, "warn", "missing-start-here", "Recommended: add START_HERE.md onboarding file", root / "START_HERE.md")
    if not (root / "COMPONENT_REGISTRATION.md").is_file():
        _add(
            diags,
            "warn",
            "missing-component-registration-guide",
            "Recommended: add COMPONENT_REGISTRATION.md to explain what/why/how of local Catalog registration",
            root / "COMPONENT_REGISTRATION.md",
        )


def _check_registry(root: Path, diags: List[DoctorDiagnostic]) -> None:
    try:
        entries = list(load_project_entries(root))
    except Exception as exc:
        _add(diags, "error", "registry-load-failed", f"Failed to load project_registry.py: {exc}", root / "project_registry.py")
        return

    if not entries:
        _add(diags, "warn", "registry-empty", "project_registry.py returned no entries", root / "project_registry.py")
        return

    keys = [e.key for e in entries]
    duplicated = sorted({k for k in keys if keys.count(k) > 1})
    if duplicated:
        _add(diags, "error", "registry-duplicate-key", f"Duplicated Catalog key(s): {', '.join(duplicated)}", root / "project_registry.py")

    for entry in entries:
        missing_usage: List[str] = []
        for field in sorted(_USAGE_KEYS):
            value = getattr(entry, field, None)
            if field == "example_entry":
                if not str(value or "").strip():
                    missing_usage.append(field)
            elif field in {"required_companions", "config_keys"}:
                # Empty tuple/list is valid: component may have no mandatory companions/config knobs.
                if value is None:
                    missing_usage.append(field)
            elif not value:
                missing_usage.append(field)
        if missing_usage:
            _add(
                diags,
                "error",
                "registry-usage-missing",
                f"[{entry.key}] missing usage fields: {', '.join(missing_usage)}",
                root / "project_registry.py",
            )

        missing_context: List[str] = []
        for field in sorted(_CONTEXT_ENTRY_KEYS):
            value = getattr(entry, field, None)
            if field == "context_notes":
                if not str(value or "").strip():
                    missing_context.append(field)
                continue
            if value is None:
                missing_context.append(field)
        if missing_context:
            _add(
                diags,
                "error",
                "registry-context-missing",
                f"[{entry.key}] missing context fields: {', '.join(missing_context)}",
                root / "project_registry.py",
            )

        try:
            _resolve_import_path(entry.import_path)
        except Exception as exc:
            _add(
                diags,
                "error",
                "registry-import-failed",
                f"[{entry.key}] import_path cannot be resolved: {entry.import_path} ({exc})",
                root / "project_registry.py",
            )

    _add(diags, "info", "registry-count", f"Catalog entries: {len(entries)}", root / "project_registry.py")


def _check_build_solver(root: Path, diags: List[DoctorDiagnostic], *, instantiate: bool) -> None:
    build_file = root / "build_solver.py"
    if not build_file.is_file():
        return

    try:
        module = _load_module_from_file("nsgablack_project_build_solver", build_file)
    except Exception as exc:
        _add(diags, "error", "build-solver-import-failed", f"Cannot import build_solver.py: {exc}", build_file)
        return

    build_fn = getattr(module, "build_solver", None)
    if not callable(build_fn):
        _add(diags, "error", "build-solver-missing", "build_solver.py has no callable build_solver()", build_file)
        return

    _add(diags, "info", "build-solver-found", "Detected build_solver()", build_file)

    if not instantiate:
        return

    try:
        sig = inspect.signature(build_fn)
        if len(sig.parameters) == 0:
            solver = build_fn()
        else:
            solver = build_fn([])
    except Exception as exc:
        _add(diags, "error", "build-solver-instantiate-failed", f"build_solver() failed: {exc}", build_file)
        return

    if solver is None:
        _add(diags, "error", "build-solver-none", "build_solver() returned None", build_file)
        return

    _add(diags, "info", "build-solver-instantiated", f"build_solver() returned: {solver.__class__.__name__}", build_file)

    try:
        from ..utils.context.context_contracts import collect_solver_contracts

        contracts = collect_solver_contracts(solver)
    except Exception as exc:
        _add(diags, "warn", "contracts-collect-failed", f"Cannot collect context contracts: {exc}", build_file)
        return

    if not contracts:
        _add(diags, "warn", "contracts-empty", "No context contracts were collected", build_file)
        return

    empty_contract_names: List[str] = []
    for name, contract in contracts:
        if not any([contract.requires, contract.provides, contract.mutates, contract.cache, contract.notes]):
            empty_contract_names.append(name)

    if empty_contract_names:
        preview = ", ".join(empty_contract_names[:6])
        suffix = "..." if len(empty_contract_names) > 6 else ""
        _add(
            diags,
            "warn",
            "contracts-not-explicit",
            f"Components without explicit context fields: {preview}{suffix}",
            build_file,
        )
    else:
        _add(diags, "info", "contracts-ok", "Collected explicit context contract fields", build_file)


def _class_has_contract(class_node: ast.ClassDef) -> bool:
    for node in class_node.body:
        if isinstance(node, ast.FunctionDef) and node.name == "get_context_contract":
            return True
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id in _CONTRACT_KEYS:
                    return True
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) and node.target.id in _CONTRACT_KEYS:
            return True
    return False


def _check_contract_source(root: Path, diags: List[DoctorDiagnostic]) -> None:
    for folder_name in _CONTRACT_CHECK_DIRS:
        folder = root / folder_name
        if not folder.is_dir():
            continue
        py_files = [p for p in folder.rglob("*.py") if p.name != "__init__.py"]
        for py_file in py_files:
            try:
                content = py_file.read_text(encoding="utf-8")
                tree = ast.parse(content, filename=str(py_file))
            except Exception as exc:
                _add(diags, "warn", "source-parse-failed", f"Cannot parse source file: {exc}", py_file)
                continue

            class_nodes = [n for n in tree.body if isinstance(n, ast.ClassDef)]
            if not class_nodes:
                continue

            for class_node in class_nodes:
                if class_node.name.startswith("_"):
                    continue
                if not _class_has_contract(class_node):
                    _add(
                        diags,
                        "warn",
                        "class-contract-missing",
                        f"Class {class_node.name} has no explicit context contract fields",
                        py_file,
                    )


def run_project_doctor(
    path: Path | str | None = None,
    *,
    instantiate_solver: bool = False,
) -> DoctorReport:
    target = Path(path).resolve() if path else Path.cwd()
    root = find_project_root(target)
    if root is None:
        root = target

    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

    diags: List[DoctorDiagnostic] = []
    _check_structure(root, diags)
    _check_registry(root, diags)
    _check_build_solver(root, diags, instantiate=instantiate_solver)
    _check_contract_source(root, diags)
    return DoctorReport(project_root=root, diagnostics=tuple(diags))


def format_doctor_report(report: DoctorReport) -> str:
    lines: List[str] = []
    lines.append(f"Project doctor: {report.project_root}")
    lines.append(
        f"summary: errors={report.error_count} warnings={report.warn_count} infos={report.info_count}"
    )
    for diag in report.diagnostics:
        prefix = {"error": "[ERROR]", "warn": "[WARN]", "info": "[INFO]"}.get(diag.level, "[INFO]")
        location = f" ({diag.path})" if diag.path else ""
        lines.append(f"{prefix} {diag.code}: {diag.message}{location}")
    return "\n".join(lines)


def iter_diagnostics_by_level(
    diagnostics: Iterable[DoctorDiagnostic],
    level: str,
) -> List[DoctorDiagnostic]:
    return [d for d in diagnostics if d.level == level]
