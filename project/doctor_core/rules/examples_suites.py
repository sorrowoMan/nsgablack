"""Examples/suites static guard rules used by project doctor."""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Callable, List, Sequence, Set

from ..model import DoctorDiagnostic


def _extract_solver_control_write_target(
    target: ast.AST,
    *,
    solver_control_fields: Set[str],
    solver_like_var_names: Set[str],
) -> tuple[str, str] | None:
    if not isinstance(target, ast.Attribute):
        return None
    attr = str(target.attr)
    if attr not in solver_control_fields:
        return None

    obj = target.value
    if isinstance(obj, ast.Name) and obj.id in solver_like_var_names:
        return obj.id, attr
    if isinstance(obj, ast.Attribute) and isinstance(obj.value, ast.Name) and obj.value.id == "self":
        if "solver" in str(obj.attr).lower():
            return f"self.{obj.attr}", attr
    return None


def check_examples_suites_solver_control_writes(
    *,
    root: Path,
    diags: List[DoctorDiagnostic],
    strict: bool,
    add: Callable[[List[DoctorDiagnostic], str, str, str, Path | None], None],
    solver_control_fields: Set[str],
    solver_like_var_names: Set[str],
    example_suite_check_dirs: Sequence[str],
) -> None:
    level = "error" if strict else "warn"
    for rel_dir in example_suite_check_dirs:
        folder = root / rel_dir
        if not folder.is_dir():
            continue
        for py_file in folder.rglob("*.py"):
            if py_file.name.startswith("__"):
                continue
            try:
                tree = ast.parse(py_file.read_text(encoding="utf-8", errors="ignore"), filename=str(py_file))
            except Exception:
                continue

            hits: List[tuple[int, str, str]] = []
            for node in ast.walk(tree):
                if isinstance(node, ast.Assign):
                    for target in node.targets:
                        match = _extract_solver_control_write_target(
                            target,
                            solver_control_fields=solver_control_fields,
                            solver_like_var_names=solver_like_var_names,
                        )
                        if match is not None:
                            obj_name, field = match
                            hits.append((int(getattr(target, "lineno", 0) or 0), obj_name, field))
                elif isinstance(node, ast.AugAssign):
                    match = _extract_solver_control_write_target(
                        node.target,
                        solver_control_fields=solver_control_fields,
                        solver_like_var_names=solver_like_var_names,
                    )
                    if match is not None:
                        obj_name, field = match
                        hits.append((int(getattr(node.target, "lineno", 0) or 0), obj_name, field))
                elif isinstance(node, ast.Call):
                    func = node.func
                    if isinstance(func, ast.Name) and func.id == "setattr" and len(node.args) >= 2:
                        obj = node.args[0]
                        key = node.args[1]
                        if isinstance(obj, ast.Name) and obj.id in solver_like_var_names:
                            if isinstance(key, ast.Constant) and isinstance(key.value, str):
                                field = str(key.value).strip()
                                if field in solver_control_fields:
                                    hits.append((int(getattr(node, "lineno", 0) or 0), obj.id, field))

            if not hits:
                continue

            uniq: List[str] = []
            seen = set()
            for line, obj_name, field in hits:
                key = (line, obj_name, field)
                if key in seen:
                    continue
                seen.add(key)
                uniq.append(f"{obj_name}.{field}@L{line}")
            add(
                diags,
                level,
                "examples-suites-direct-solver-control-write",
                (
                    "Examples/suites must use solver control-plane methods "
                    "(set_adapter/set_bias_module/set_bias_enabled/set_max_steps/set_solver_hyperparams); "
                    "direct assignments are forbidden: "
                    + ", ".join(uniq[:10])
                    + (" ..." if len(uniq) > 10 else "")
                ),
                py_file,
            )

