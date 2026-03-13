"""Registry integrity checks used by project doctor."""

from __future__ import annotations

import importlib
from pathlib import Path
from typing import Callable, Iterable, List

from ..model import DoctorDiagnostic


def _resolve_import_path(import_path: str):
    module_path, sep, attr_path = str(import_path).partition(":")
    if not module_path or not sep or not attr_path:
        raise ValueError(f"Invalid import_path: {import_path!r} (expected 'module:attr')")
    module = importlib.import_module(module_path)
    obj = module
    for part in attr_path.split("."):
        obj = getattr(obj, part)
    return obj


def check_registry(
    *,
    root: Path,
    diags: List[DoctorDiagnostic],
    add: Callable[[List[DoctorDiagnostic], str, str, str, Path | None], None],
    load_project_entries: Callable[[Path], Iterable[object]],
    usage_keys: Iterable[str],
    context_entry_keys: Iterable[str],
) -> None:
    registry_file = root / "project_registry.py"
    if not registry_file.is_file():
        add(diags, "info", "registry-skip", "Skip registry checks (project_registry.py not found).", registry_file)
        return
    try:
        entries = list(load_project_entries(root))
    except Exception as exc:
        add(diags, "error", "registry-load-failed", f"Failed to load project_registry.py: {exc}", registry_file)
        return

    if not entries:
        add(diags, "warn", "registry-empty", "project_registry.py returned no entries", registry_file)
        return

    keys = [getattr(e, "key", None) for e in entries]
    duplicated = sorted({k for k in keys if k is not None and keys.count(k) > 1})
    if duplicated:
        add(diags, "error", "registry-duplicate-key", f"Duplicated Catalog key(s): {', '.join(duplicated)}", registry_file)

    usage_fields = sorted(set(str(k) for k in usage_keys))
    context_fields = sorted(set(str(k) for k in context_entry_keys))

    for entry in entries:
        entry_key = str(getattr(entry, "key", "unknown"))
        missing_usage: List[str] = []
        for field in usage_fields:
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
            add(
                diags,
                "error",
                "registry-usage-missing",
                f"[{entry_key}] missing usage fields: {', '.join(missing_usage)}",
                registry_file,
            )

        missing_context: List[str] = []
        for field in context_fields:
            value = getattr(entry, field, None)
            if field == "context_notes":
                if not str(value or "").strip():
                    missing_context.append(field)
                continue
            if value is None:
                missing_context.append(field)
        if missing_context:
            add(
                diags,
                "error",
                "registry-context-missing",
                f"[{entry_key}] missing context fields: {', '.join(missing_context)}",
                registry_file,
            )

        try:
            _resolve_import_path(str(getattr(entry, "import_path", "")))
        except Exception as exc:
            add(
                diags,
                "error",
                "registry-import-failed",
                f"[{entry_key}] import_path cannot be resolved: {getattr(entry, 'import_path', '')} ({exc})",
                registry_file,
            )

    add(diags, "info", "registry-count", f"Catalog entries: {len(entries)}", registry_file)
