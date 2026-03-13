"""Adapter-layer purity checks used by project doctor."""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Callable, List

from ..model import DoctorDiagnostic


def check_adapter_layer_purity(
    *,
    root: Path,
    diags: List[DoctorDiagnostic],
    strict: bool,
    add: Callable[[List[DoctorDiagnostic], str, str, str, Path | None], None],
) -> None:
    adapter_roots = [root / "adapter", root / "core" / "adapters"]
    hits: List[str] = []

    for adapter_root in adapter_roots:
        if not adapter_root.is_dir():
            continue
        for py_file in adapter_root.rglob("*.py"):
            if py_file.name.startswith("__"):
                continue
            try:
                tree = ast.parse(py_file.read_text(encoding="utf-8", errors="ignore"))
            except Exception:
                continue

            imported_algorithmic_bias = False
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom):
                    module = str(node.module or "")
                    if "bias.core.base" in module:
                        for alias in node.names:
                            if alias.name == "AlgorithmicBias":
                                imported_algorithmic_bias = True
                                break
                if imported_algorithmic_bias:
                    break

            for node in tree.body:
                if not isinstance(node, ast.ClassDef):
                    continue
                if node.name.endswith("Bias"):
                    hits.append(f"{py_file}:{node.name}")
                    continue
                if imported_algorithmic_bias:
                    for base in node.bases:
                        base_text = ast.unparse(base)
                        if "AlgorithmicBias" in base_text:
                            hits.append(f"{py_file}:{node.name}")
                            break

    if not hits:
        return

    preview = ", ".join(hits[:6])
    suffix = " ..." if len(hits) > 6 else ""
    add(
        diags,
        "error" if strict else "warn",
        "adapter-layer-purity",
        f"Adapter layer contains bias-like classes; use AlgorithmAdapter propose/update pattern: {preview}{suffix}",
        root,
    )
