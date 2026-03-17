"""L0/L3/L4 runtime governance checks for project doctor."""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Callable, List

from ..model import DoctorDiagnostic


def _iter_py_files(root: Path) -> List[Path]:
    if not root.exists():
        return []
    out: List[Path] = []
    for p in root.rglob("*.py"):
        if "__pycache__" in p.parts:
            continue
        out.append(p)
    return out


def _parse_file(path: Path) -> ast.AST | None:
    try:
        return ast.parse(path.read_text(encoding="utf-8-sig"))
    except Exception:
        return None


def _is_plugin_class(node: ast.ClassDef) -> bool:
    for base in node.bases:
        if isinstance(base, ast.Name) and base.id == "Plugin":
            return True
        if isinstance(base, ast.Attribute) and base.attr == "Plugin":
            return True
    return False


def check_no_plugin_evaluation_short_circuit(
    *,
    root: Path,
    diags: List[DoctorDiagnostic],
    strict: bool,
    add: Callable[[List[DoctorDiagnostic], str, str, str, Path | None], None],
) -> None:
    plugins_dir = root / "plugins"
    if not plugins_dir.exists():
        return
    for file in _iter_py_files(plugins_dir):
        tree = _parse_file(file)
        if tree is None:
            continue
        hits: List[str] = []
        for node in ast.walk(tree):
            if not isinstance(node, ast.ClassDef):
                continue
            if not _is_plugin_class(node):
                continue
            methods = {n.name for n in node.body if isinstance(n, ast.FunctionDef)}
            if "evaluate_individual" in methods or "evaluate_population" in methods:
                hits.append(f"{node.name}@L{int(getattr(node, 'lineno', 0) or 0)}")
        if not hits:
            continue
        add(
            diags,
            "error" if strict else "warn",
            "plugin-eval-short-circuit-forbidden",
            (
                "Evaluation short-circuit must use L4 EvaluationProvider, not Plugin hooks: "
                + ", ".join(hits[:8])
                + (" ..." if len(hits) > 8 else "")
            ),
            file,
        )


def check_runtime_governance_runtime_state(
    *,
    solver: object,
    build_file: Path,
    diags: List[DoctorDiagnostic],
    strict: bool,
    add: Callable[[List[DoctorDiagnostic], str, str, str, Path | None], None],
) -> None:
    runtime_controller = getattr(solver, "runtime_controller", None)
    if runtime_controller is not None and hasattr(runtime_controller, "validate_configuration"):
        try:
            runtime_controller.validate_configuration()
        except Exception as exc:
            add(
                diags,
                "error" if strict else "warn",
                "runtime-controller-conflict",
                f"Runtime controller configuration conflict: {exc}",
                build_file,
            )

    mediator = getattr(solver, "evaluation_mediator", None)
    if mediator is None:
        return
    providers = ()
    list_providers = getattr(mediator, "list_providers", None)
    if callable(list_providers):
        try:
            providers = tuple(list_providers())
        except Exception:
            providers = ()
    allow_approx = bool(getattr(getattr(mediator, "config", None), "allow_approximate", False))
    approx_names = [
        str(getattr(p, "name", p.__class__.__name__))
        for p in providers
        if str(getattr(p, "semantic_mode", "")).strip().lower() == "approximate"
    ]
    if approx_names and not allow_approx:
        add(
            diags,
            "warn",
            "l4-approx-provider-disabled",
            (
                "Approximate providers registered while allow_approximate=False: "
                + ", ".join(approx_names[:8])
                + (" ..." if len(approx_names) > 8 else "")
            ),
            build_file,
        )
