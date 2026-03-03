from __future__ import annotations

import ast
from pathlib import Path


_ALLOWED_LEVELS = {"L0", "L1", "L2"}


def _iter_adapter_classes() -> list[tuple[Path, ast.ClassDef]]:
    out: list[tuple[Path, ast.ClassDef]] = []
    root = Path(__file__).resolve().parents[1] / "adapters"
    for py_file in sorted(root.glob("*.py")):
        if py_file.name == "__init__.py":
            continue
        tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
        for node in tree.body:
            if isinstance(node, ast.ClassDef) and node.name.endswith("Adapter"):
                out.append((py_file, node))
    return out


def _class_attrs(node: ast.ClassDef) -> dict[str, ast.expr]:
    attrs: dict[str, ast.expr] = {}
    for stmt in node.body:
        if isinstance(stmt, ast.Assign):
            for target in stmt.targets:
                if isinstance(target, ast.Name):
                    attrs[target.id] = stmt.value
        elif isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name) and stmt.value is not None:
            attrs[stmt.target.id] = stmt.value
    return attrs


def _literal_str(expr: ast.expr) -> str | None:
    if isinstance(expr, ast.Constant) and isinstance(expr.value, str):
        return str(expr.value)
    return None


def test_stateful_adapters_declare_recovery_level_and_roundtrip_methods():
    for path, class_node in _iter_adapter_classes():
        methods = {
            stmt.name
            for stmt in class_node.body
            if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef))
        }
        has_get = "get_state" in methods
        has_set = "set_state" in methods
        if not (has_get or has_set):
            continue
        assert has_get and has_set, f"{path}:{class_node.name} must define both get_state/set_state"

        attrs = _class_attrs(class_node)
        assert "state_recovery_level" in attrs, f"{path}:{class_node.name} missing state_recovery_level"
        level = _literal_str(attrs["state_recovery_level"])
        assert level is not None, f"{path}:{class_node.name} state_recovery_level must be a string literal"
        assert level in _ALLOWED_LEVELS, f"{path}:{class_node.name} invalid state_recovery_level={level!r}"


def test_non_l0_stateful_adapters_declare_recovery_notes():
    for path, class_node in _iter_adapter_classes():
        attrs = _class_attrs(class_node)
        level_expr = attrs.get("state_recovery_level")
        if level_expr is None:
            continue
        level = _literal_str(level_expr)
        if level is None or level == "L0":
            continue
        notes_expr = attrs.get("state_recovery_notes")
        notes = _literal_str(notes_expr) if notes_expr is not None else None
        assert notes, f"{path}:{class_node.name} with {level} should declare non-empty state_recovery_notes"
