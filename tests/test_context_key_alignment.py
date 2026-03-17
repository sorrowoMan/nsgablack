from __future__ import annotations

import ast
from pathlib import Path

from nsgablack.core.state.context_keys import CANONICAL_CONTEXT_KEYS, normalize_context_key


ROOTS = (
    Path("adapters"),
    Path("plugins"),
    Path("representation"),
    Path("bias"),
    Path("utils"),
)


def _iter_py_files():
    for root in ROOTS:
        if not root.exists():
            continue
        yield from root.rglob("*.py")


def test_no_raw_context_literal_key_access() -> None:
    issues: list[str] = []
    for path in _iter_py_files():
        text = path.read_text(encoding="utf-8-sig")
        tree = ast.parse(text)
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "get":
                if isinstance(node.func.value, ast.Name) and node.func.value.id == "context" and node.args:
                    arg0 = node.args[0]
                    if isinstance(arg0, ast.Constant) and isinstance(arg0.value, str):
                        issues.append(f"{path}:{node.lineno}:{arg0.value}")
            if isinstance(node, ast.Subscript):
                if isinstance(node.value, ast.Name) and node.value.id == "context":
                    key = node.slice
                    if isinstance(key, ast.Constant) and isinstance(key.value, str):
                        issues.append(f"{path}:{node.lineno}:{key.value}")

    assert not issues, "Raw context string keys found; use canonical constants:\n" + "\n".join(issues)


def test_contract_key_literals_are_canonical() -> None:
    attrs = {
        "context_requires",
        "context_provides",
        "context_mutates",
        "context_cache",
        "requires_context_keys",
        "runtime_requires",
        "runtime_provides",
        "runtime_mutates",
        "runtime_cache",
    }
    issues: list[str] = []
    for path in _iter_py_files():
        text = path.read_text(encoding="utf-8-sig")
        tree = ast.parse(text)
        for node in ast.walk(tree):
            if not isinstance(node, ast.Assign):
                continue
            if len(node.targets) != 1 or not isinstance(node.targets[0], ast.Name):
                continue
            name = node.targets[0].id
            if name not in attrs:
                continue
            value = node.value
            literals: list[str] = []
            if isinstance(value, (ast.Tuple, ast.List, ast.Set)):
                for item in value.elts:
                    if isinstance(item, ast.Constant) and isinstance(item.value, str):
                        literals.append(item.value)
            elif isinstance(value, ast.Constant) and isinstance(value.value, str):
                literals.append(value.value)
            for key in literals:
                normalized = normalize_context_key(key)
                if normalized.startswith("metrics."):
                    continue
                if normalized not in CANONICAL_CONTEXT_KEYS:
                    issues.append(f"{path}:{node.lineno}:{name}:{key}")

    assert not issues, "Non-canonical contract key literals found:\n" + "\n".join(issues)
