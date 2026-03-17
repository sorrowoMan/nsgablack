"""Runtime/control-plane static guard rules used by project doctor."""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Callable, List, Sequence, Set

from ..model import DoctorDiagnostic


def _is_solver_ref(node: ast.AST) -> bool:
    if isinstance(node, ast.Name) and node.id == "solver":
        return True
    return (
        isinstance(node, ast.Attribute)
        and isinstance(node.value, ast.Name)
        and node.value.id == "self"
        and node.attr == "solver"
    )


class _SolverMirrorWriteVisitor(ast.NodeVisitor):
    def __init__(self, *, forbidden_solver_mirror_attrs: Set[str]) -> None:
        self.hits: List[tuple[int, str]] = []
        self._forbidden_solver_mirror_attrs = forbidden_solver_mirror_attrs

    def visit_Assign(self, node: ast.Assign) -> None:  # noqa: N802
        for target in node.targets:
            self._check_target(target)
        self.generic_visit(node)

    def visit_AugAssign(self, node: ast.AugAssign) -> None:  # noqa: N802
        self._check_target(node.target)
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:  # noqa: N802
        func = node.func
        if isinstance(func, ast.Name) and func.id == "setattr" and len(node.args) >= 2:
            obj = node.args[0]
            key = node.args[1]
            if isinstance(obj, ast.Name) and obj.id == "solver":
                if isinstance(key, ast.Constant) and isinstance(key.value, str):
                    attr = key.value.strip()
                    if attr in self._forbidden_solver_mirror_attrs:
                        self.hits.append((int(getattr(node, "lineno", 0) or 0), attr))
        self.generic_visit(node)

    def _check_target(self, target: ast.expr) -> None:
        if isinstance(target, ast.Attribute) and isinstance(target.value, ast.Name) and target.value.id == "solver":
            attr = str(target.attr)
            if attr in self._forbidden_solver_mirror_attrs:
                self.hits.append((int(getattr(target, "lineno", 0) or 0), attr))


def check_forbidden_solver_mirror_writes(
    *,
    tree: ast.AST,
    path: Path,
    diags: List[DoctorDiagnostic],
    strict: bool,
    add: Callable[[List[DoctorDiagnostic], str, str, str, Path | None], None],
    forbidden_solver_mirror_attrs: Set[str],
) -> None:
    visitor = _SolverMirrorWriteVisitor(forbidden_solver_mirror_attrs=forbidden_solver_mirror_attrs)
    visitor.visit(tree)
    if not visitor.hits:
        return
    uniq: List[str] = []
    seen = set()
    for line, attr in visitor.hits:
        key = (line, attr)
        if key in seen:
            continue
        seen.add(key)
        uniq.append(f"{attr}@L{line}")
    add(
        diags,
        "error" if strict else "warn",
        "solver-mirror-write",
        "Forbidden solver mirror writes found (use solver control-plane projection instead): "
        + ", ".join(uniq[:8])
        + (" ..." if len(uniq) > 8 else ""),
        path,
    )


def _extract_runtime_state_field_from_target(target: ast.AST, *, runtime_state_fields: Set[str]) -> str | None:
    if isinstance(target, ast.Attribute) and _is_solver_ref(target.value):
        attr = str(target.attr)
        if attr in runtime_state_fields:
            return attr
    if isinstance(target, ast.Subscript):
        value = target.value
        if isinstance(value, ast.Attribute) and _is_solver_ref(value.value):
            attr = str(value.attr)
            if attr in runtime_state_fields:
                return attr
    return None


def _extract_runtime_private_call_name(call_node: ast.Call) -> str | None:
    func = call_node.func
    if not isinstance(func, ast.Attribute):
        return None
    method = str(func.attr)
    if not method.startswith("_"):
        return None
    owner = func.value
    if isinstance(owner, ast.Attribute) and owner.attr == "runtime" and _is_solver_ref(owner.value):
        return method
    return None


def check_runtime_private_calls(
    *,
    tree: ast.AST,
    path: Path,
    diags: List[DoctorDiagnostic],
    strict: bool,
    add: Callable[[List[DoctorDiagnostic], str, str, str, Path | None], None],
) -> None:
    hits: List[tuple[int, str]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        method = _extract_runtime_private_call_name(node)
        if method is not None:
            hits.append((int(getattr(node, "lineno", 0) or 0), method))
    if not hits:
        return
    uniq: List[str] = []
    seen = set()
    for line, method in hits:
        key = (line, method)
        if key in seen:
            continue
        seen.add(key)
        uniq.append(f"{method}@L{line}")
    add(
        diags,
        "error" if strict else "warn",
        "runtime-private-call",
        (
            "Private runtime calls detected (solver.runtime._*). "
            "Use public solver control-plane APIs instead: "
            + ", ".join(uniq[:10])
            + (" ..." if len(uniq) > 10 else "")
        ),
        path,
    )


def check_runtime_bypass_writes(
    *,
    tree: ast.AST,
    path: Path,
    diags: List[DoctorDiagnostic],
    strict: bool,
    add: Callable[[List[DoctorDiagnostic], str, str, str, Path | None], None],
    runtime_state_fields: Set[str],
) -> None:
    if not strict:
        return
    hits: List[tuple[int, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                attr = _extract_runtime_state_field_from_target(target, runtime_state_fields=runtime_state_fields)
                if attr is not None:
                    hits.append((int(getattr(target, "lineno", 0) or 0), attr))
        elif isinstance(node, ast.AugAssign):
            attr = _extract_runtime_state_field_from_target(node.target, runtime_state_fields=runtime_state_fields)
            if attr is not None:
                hits.append((int(getattr(node.target, "lineno", 0) or 0), attr))
        elif isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name) and func.id == "setattr" and len(node.args) >= 2:
                obj = node.args[0]
                key = node.args[1]
                if _is_solver_ref(obj) and isinstance(key, ast.Constant) and isinstance(key.value, str):
                    attr = str(key.value).strip()
                    if attr in runtime_state_fields:
                        hits.append((int(getattr(node, "lineno", 0) or 0), attr))
    if not hits:
        return
    uniq: List[str] = []
    seen = set()
    for line, attr in hits:
        key = (line, attr)
        if key in seen:
            continue
        seen.add(key)
        uniq.append(f"{attr}@L{line}")
    add(
        diags,
        "error",
        "runtime-bypass-write",
        "Direct solver runtime-state writes detected; route through solver control-plane APIs "
        "(solver.set_*, increment_evaluation_count, write_population_snapshot, context/snapshot projection): "
        + ", ".join(uniq[:10])
        + (" ..." if len(uniq) > 10 else ""),
        path,
    )


def _extract_solver_field_from_target(target: ast.AST, *, plugin_state_fields: Set[str]) -> str | None:
    if isinstance(target, ast.Attribute) and _is_solver_ref(target.value):
        attr = str(target.attr)
        if attr in plugin_state_fields:
            return attr
    if isinstance(target, ast.Subscript):
        value = target.value
        if isinstance(value, ast.Attribute) and _is_solver_ref(value.value):
            attr = str(value.attr)
            if attr in plugin_state_fields:
                return attr
    return None


def check_plugin_solver_state_access(
    *,
    tree: ast.AST,
    path: Path,
    diags: List[DoctorDiagnostic],
    add: Callable[[List[DoctorDiagnostic], str, str, str, Path | None], None],
    plugin_state_fields: Set[str],
) -> None:
    reads: List[tuple[int, str]] = []
    writes: List[tuple[int, str]] = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                attr = _extract_solver_field_from_target(target, plugin_state_fields=plugin_state_fields)
                if attr is not None:
                    writes.append((int(getattr(target, "lineno", 0) or 0), attr))
        elif isinstance(node, ast.AugAssign):
            attr = _extract_solver_field_from_target(node.target, plugin_state_fields=plugin_state_fields)
            if attr is not None:
                writes.append((int(getattr(node.target, "lineno", 0) or 0), attr))
        elif isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name) and func.id == "setattr" and len(node.args) >= 2:
                obj = node.args[0]
                key = node.args[1]
                if _is_solver_ref(obj) and isinstance(key, ast.Constant) and isinstance(key.value, str):
                    attr = str(key.value).strip()
                    if attr in plugin_state_fields:
                        writes.append((int(getattr(node, "lineno", 0) or 0), attr))
            if isinstance(func, ast.Name) and func.id == "getattr" and len(node.args) >= 2:
                obj = node.args[0]
                key = node.args[1]
                if _is_solver_ref(obj) and isinstance(key, ast.Constant) and isinstance(key.value, str):
                    attr = str(key.value).strip()
                    if attr in plugin_state_fields:
                        reads.append((int(getattr(node, "lineno", 0) or 0), attr))
        elif isinstance(node, ast.Attribute):
            if _is_solver_ref(node.value):
                attr = str(node.attr)
                if attr in plugin_state_fields:
                    reads.append((int(getattr(node, "lineno", 0) or 0), attr))

    if not reads and not writes:
        return

    def _uniq(items: List[tuple[int, str]]) -> List[str]:
        seen = set()
        out: List[str] = []
        for line, attr in items:
            key = (line, attr)
            if key in seen:
                continue
            seen.add(key)
            out.append(f"{attr}@L{line}")
        return out

    read_list = _uniq(reads)
    write_list = _uniq(writes)
    parts: List[str] = []
    if read_list:
        parts.append("reads: " + ", ".join(read_list[:8]) + (" ..." if len(read_list) > 8 else ""))
    if write_list:
        parts.append("writes: " + ", ".join(write_list[:8]) + (" ..." if len(write_list) > 8 else ""))

    add(
        diags,
        "error",
        "plugin-direct-solver-state-access",
        "Plugins must not directly access solver population/objectives/constraint_violations under --strict; "
        "use get_population_snapshot()/commit_population_snapshot(). "
        + " | ".join(parts),
        path,
    )


