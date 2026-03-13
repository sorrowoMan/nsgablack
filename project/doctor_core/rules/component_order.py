"""Component order static checks for project doctor."""

from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Dict, Iterable, List, Optional, Sequence, Set, Tuple

from ....core.solver_helpers import ComponentDependencyScheduler, ComponentOrderError
from ..model import DoctorDiagnostic


@dataclass
class _OrderAction:
    kind: str  # add | set
    line: int
    component_name: Optional[str]
    priority: int = 0
    depends_on: Optional[Set[str]] = None
    before: Optional[Set[str]] = None
    after: Optional[Set[str]] = None
    nonliteral: bool = False


_CLASS_ORDER_ATTRS = ("depends_on_plugins", "before_plugins", "after_plugins")


@dataclass
class _PluginClassSpec:
    path: Path
    line: int
    class_name: str
    component_name: str
    priority: int
    depends_on: Set[str]
    before: Set[str]
    after: Set[str]
    has_order_attrs: bool
    nonliteral_order_attrs: Set[str]


def _literal_string_set(node: ast.AST) -> Tuple[Optional[Set[str]], bool]:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return {str(node.value).strip()}, False
    if isinstance(node, (ast.List, ast.Tuple, ast.Set)):
        out: Set[str] = set()
        for item in node.elts:
            if not isinstance(item, ast.Constant) or not isinstance(item.value, str):
                return None, True
            text = str(item.value).strip()
            if text:
                out.add(text)
        return out, False
    return None, True


def _literal_int(node: ast.AST) -> Optional[int]:
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return int(node.value)
    return None


def _infer_call_name_and_priority(expr: ast.AST) -> Tuple[Optional[str], int]:
    if isinstance(expr, ast.Constant) and isinstance(expr.value, str):
        return str(expr.value).strip(), 0
    if not isinstance(expr, ast.Call):
        return None, 0

    plugin_name: Optional[str] = None
    priority = 0
    for kw in expr.keywords:
        if kw.arg == "name" and isinstance(kw.value, ast.Constant) and isinstance(kw.value.value, str):
            plugin_name = str(kw.value.value).strip()
        elif kw.arg == "priority":
            iv = _literal_int(kw.value)
            if iv is not None:
                priority = int(iv)
    if not plugin_name:
        func = expr.func
        if isinstance(func, ast.Name):
            plugin_name = str(func.id).strip()
        elif isinstance(func, ast.Attribute):
            plugin_name = str(func.attr).strip()
    return plugin_name, int(priority)


class _OrderActionCollector(ast.NodeVisitor):
    def __init__(self) -> None:
        self.actions: List[_OrderAction] = []

    def visit_Call(self, node: ast.Call) -> None:  # noqa: N802
        func = node.func
        if isinstance(func, ast.Attribute):
            method = str(func.attr)
            if method == "add_plugin":
                self.actions.append(self._parse_add_plugin(node))
            elif method == "set_plugin_order":
                self.actions.append(self._parse_set_plugin_order(node))
        self.generic_visit(node)

    def _parse_add_plugin(self, node: ast.Call) -> _OrderAction:
        name: Optional[str] = None
        priority = 0
        nonliteral = False
        if node.args:
            name, priority = _infer_call_name_and_priority(node.args[0])
            if not name:
                nonliteral = True
        else:
            for kw in node.keywords:
                if kw.arg == "plugin":
                    name, priority = _infer_call_name_and_priority(kw.value)
                    if not name:
                        nonliteral = True
                    break

        depends_on: Optional[Set[str]] = None
        before: Optional[Set[str]] = None
        after: Optional[Set[str]] = None
        for kw in node.keywords:
            if kw.arg not in {"depends_on", "before", "after"}:
                continue
            values, bad = _literal_string_set(kw.value)
            if bad:
                nonliteral = True
            if kw.arg == "depends_on":
                depends_on = values
            elif kw.arg == "before":
                before = values
            elif kw.arg == "after":
                after = values
        return _OrderAction(
            kind="add",
            line=int(getattr(node, "lineno", 0) or 0),
            component_name=name,
            priority=int(priority),
            depends_on=depends_on,
            before=before,
            after=after,
            nonliteral=bool(nonliteral),
        )

    def _parse_set_plugin_order(self, node: ast.Call) -> _OrderAction:
        name: Optional[str] = None
        nonliteral = False
        if node.args and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str):
            name = str(node.args[0].value).strip()
        elif node.args:
            nonliteral = True
        else:
            found_keyword = False
            for kw in node.keywords:
                if kw.arg != "plugin_name":
                    continue
                found_keyword = True
                if isinstance(kw.value, ast.Constant) and isinstance(kw.value.value, str):
                    name = str(kw.value.value).strip()
                else:
                    nonliteral = True
                break
            if not found_keyword:
                nonliteral = True

        if not name and not nonliteral:
            nonliteral = True

        depends_on: Optional[Set[str]] = None
        before: Optional[Set[str]] = None
        after: Optional[Set[str]] = None
        for kw in node.keywords:
            if kw.arg not in {"depends_on", "before", "after"}:
                continue
            values, bad = _literal_string_set(kw.value)
            if bad:
                nonliteral = True
            if kw.arg == "depends_on":
                depends_on = values
            elif kw.arg == "before":
                before = values
            elif kw.arg == "after":
                after = values
        return _OrderAction(
            kind="set",
            line=int(getattr(node, "lineno", 0) or 0),
            component_name=name,
            depends_on=depends_on,
            before=before,
            after=after,
            nonliteral=bool(nonliteral),
        )


def _classify_component_order_error(exc: Exception) -> str:
    msg = str(exc).lower()
    if "unknown component" in msg:
        return "component-order-unknown-ref"
    if "cycle" in msg:
        return "component-order-cycle"
    if "priority conflict" in msg:
        return "component-order-priority-conflict"
    if "contradictory" in msg:
        return "component-order-mutual-conflict"
    if "itself" in msg:
        return "component-order-self-ref"
    return "component-order-invalid"


def _extract_class_string_list_assignments(class_node: ast.ClassDef) -> Tuple[Dict[str, Set[str]], Set[str]]:
    out: Dict[str, Set[str]] = {}
    nonliteral: Set[str] = set()
    for stmt in class_node.body:
        if isinstance(stmt, ast.Assign) and len(stmt.targets) == 1 and isinstance(stmt.targets[0], ast.Name):
            attr = str(stmt.targets[0].id)
            if attr in _CLASS_ORDER_ATTRS:
                vals, bad = _literal_string_set(stmt.value)
                if bad or vals is None:
                    nonliteral.add(attr)
                    continue
                out[attr] = vals
        elif isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name):
            attr = str(stmt.target.id)
            if attr in _CLASS_ORDER_ATTRS and stmt.value is not None:
                vals, bad = _literal_string_set(stmt.value)
                if bad or vals is None:
                    nonliteral.add(attr)
                    continue
                out[attr] = vals
    return out, nonliteral


def _extract_class_literal_int_assignments(class_node: ast.ClassDef, attr_name: str) -> Optional[int]:
    for stmt in class_node.body:
        if isinstance(stmt, ast.Assign) and len(stmt.targets) == 1 and isinstance(stmt.targets[0], ast.Name):
            if str(stmt.targets[0].id) == attr_name:
                iv = _literal_int(stmt.value)
                if iv is not None:
                    return int(iv)
        if isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name):
            if str(stmt.target.id) == attr_name and stmt.value is not None:
                iv = _literal_int(stmt.value)
                if iv is not None:
                    return int(iv)
    return None


def _infer_component_name_and_priority(class_node: ast.ClassDef) -> Tuple[str, int]:
    # Conservative defaults: class name + priority 0.
    component_name = str(class_node.name)
    priority = int(_extract_class_literal_int_assignments(class_node, "priority") or 0)

    for fn in class_node.body:
        if not isinstance(fn, ast.FunctionDef) or fn.name != "__init__":
            continue
        for call in ast.walk(fn):
            if not isinstance(call, ast.Call):
                continue
            if not isinstance(call.func, ast.Attribute) or str(call.func.attr) != "__init__":
                continue
            for kw in call.keywords:
                if kw.arg == "name" and isinstance(kw.value, ast.Constant) and isinstance(kw.value.value, str):
                    text = str(kw.value.value).strip()
                    if text:
                        component_name = text
                elif kw.arg == "priority":
                    iv = _literal_int(kw.value)
                    if iv is not None:
                        priority = int(iv)
    return component_name, int(priority)


def _collect_plugin_class_specs(
    py_files: Sequence[Path],
    diags: List[DoctorDiagnostic],
    add,
) -> List[_PluginClassSpec]:
    specs: List[_PluginClassSpec] = []
    for py_file in py_files:
        try:
            tree = ast.parse(py_file.read_text(encoding="utf-8-sig"), filename=str(py_file))
        except Exception as exc:
            add(
                diags,
                "warn",
                "source-parse-failed",
                f"Cannot parse source file: {exc}",
                py_file,
            )
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.ClassDef):
                continue
            component_name, priority = _infer_component_name_and_priority(node)
            refs, nonliteral = _extract_class_string_list_assignments(node)
            specs.append(
                _PluginClassSpec(
                    path=py_file,
                    line=int(getattr(node, "lineno", 0) or 0),
                    class_name=str(node.name),
                    component_name=str(component_name),
                    priority=int(priority),
                    depends_on=set(refs.get("depends_on_plugins", set())),
                    before=set(refs.get("before_plugins", set())),
                    after=set(refs.get("after_plugins", set())),
                    has_order_attrs=bool(refs) or bool(nonliteral),
                    nonliteral_order_attrs=set(nonliteral),
                )
            )
    return specs


def _collect_declared_plugin_names(py_files: Sequence[Path], diags: List[DoctorDiagnostic], add) -> Set[str]:
    names: Set[str] = set()
    for py_file in py_files:
        try:
            tree = ast.parse(py_file.read_text(encoding="utf-8-sig"), filename=str(py_file))
        except Exception as exc:
            add(
                diags,
                "warn",
                "source-parse-failed",
                f"Cannot parse source file: {exc}",
                py_file,
            )
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.ClassDef):
                continue
            # Conservative static name inference: class name itself is always available.
            names.add(str(node.name))
            for fn in node.body:
                if not isinstance(fn, ast.FunctionDef) or fn.name != "__init__":
                    continue
                for call in ast.walk(fn):
                    if not isinstance(call, ast.Call):
                        continue
                    if isinstance(call.func, ast.Attribute) and str(call.func.attr) == "__init__":
                        for kw in call.keywords:
                            if (
                                kw.arg == "name"
                                and isinstance(kw.value, ast.Constant)
                                and isinstance(kw.value.value, str)
                            ):
                                names.add(str(kw.value.value).strip())
    return names


def _check_plugin_class_order_declarations(
    *,
    root: Path,
    diags: List[DoctorDiagnostic],
    strict: bool,
    add: Callable[[List[DoctorDiagnostic], str, str, str, Path | None], None],
) -> None:
    plugins_dir = root / "plugins"
    if not plugins_dir.is_dir():
        return
    py_files = sorted([p for p in plugins_dir.rglob("*.py") if p.is_file()])
    class_specs = _collect_plugin_class_specs(py_files, diags, add)
    if not class_specs:
        return

    declared_names = _collect_declared_plugin_names(py_files, diags, add)
    level = "error" if strict else "warn"
    scheduler = ComponentDependencyScheduler()
    registered_names: Set[str] = set()

    # Register all known plugin component names first so cross-file references are resolvable.
    for spec in class_specs:
        scheduler.register_component(spec.component_name, priority=int(spec.priority))
        registered_names.add(spec.component_name)
    for alias_name in sorted(declared_names):
        if alias_name in registered_names:
            continue
        scheduler.register_component(alias_name, priority=0)

    # Alias map lets declarations reference class names or explicit runtime names.
    alias_map: Dict[str, str] = {}
    for spec in class_specs:
        alias_map.setdefault(spec.class_name, spec.component_name)
        alias_map.setdefault(spec.component_name, spec.component_name)

    for spec in class_specs:
        if not spec.has_order_attrs:
            continue
        if spec.nonliteral_order_attrs:
            add(
                diags,
                level,
                "component-order-nonliteral",
                (
                    f"Plugin class '{spec.class_name}' has non-literal order declarations at L{spec.line}: "
                    + ", ".join(sorted(spec.nonliteral_order_attrs))
                ),
                spec.path,
            )
        depends_on = {alias_map.get(x, x) for x in spec.depends_on}
        before = {alias_map.get(x, x) for x in spec.before}
        after = {alias_map.get(x, x) for x in spec.after}
        try:
            scheduler.set_constraints(
                spec.component_name,
                depends_on=depends_on,
                before=before,
                after=after,
            )
        except ComponentOrderError as exc:
            add(
                diags,
                level,
                _classify_component_order_error(exc),
                f"Plugin class '{spec.class_name}' ({spec.component_name}) @L{spec.line}: {exc}",
                spec.path,
            )

    try:
        scheduler.resolve_order_strict()
    except ComponentOrderError as exc:
        add(
            diags,
            level,
            _classify_component_order_error(exc),
            f"Plugin class order invalid: {exc}",
            plugins_dir,
        )


def check_component_order_constraints(
    *,
    root: Path,
    diags: List[DoctorDiagnostic],
    strict: bool,
    add: Callable[[List[DoctorDiagnostic], str, str, str, Path | None], None],
) -> None:
    level = "error" if strict else "warn"
    build_file = root / "build_solver.py"
    if build_file.is_file():
        try:
            tree = ast.parse(build_file.read_text(encoding="utf-8-sig"), filename=str(build_file))
        except Exception as exc:
            add(
                diags,
                "warn",
                "source-parse-failed",
                f"Cannot parse source file: {exc}",
                build_file,
            )
            tree = None

        if tree is not None:
            collector = _OrderActionCollector()
            collector.visit(tree)
            scheduler = ComponentDependencyScheduler()
            for action in collector.actions:
                if action.nonliteral:
                    add(
                        diags,
                        level,
                        "component-order-nonliteral",
                        (
                            f"Non-literal component order declaration at L{action.line}; "
                            "use string literals in add_plugin/set_plugin_order for static checks."
                        ),
                        build_file,
                    )
                if not action.component_name:
                    continue
                try:
                    if action.kind == "add":
                        scheduler.register_component(
                            action.component_name,
                            priority=int(action.priority),
                        )
                    scheduler.set_constraints(
                        action.component_name,
                        depends_on=action.depends_on,
                        before=action.before,
                        after=action.after,
                    )
                except ComponentOrderError as exc:
                    add(
                        diags,
                        level,
                        _classify_component_order_error(exc),
                        f"{exc} @L{action.line}",
                        build_file,
                    )
            try:
                scheduler.resolve_order_strict()
            except ComponentOrderError as exc:
                add(
                    diags,
                    level,
                    _classify_component_order_error(exc),
                    f"{exc} @L1",
                    build_file,
                )

    _check_plugin_class_order_declarations(
        root=root,
        diags=diags,
        strict=bool(strict),
        add=add,
    )
