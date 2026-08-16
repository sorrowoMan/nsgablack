from __future__ import annotations

import ast
from pathlib import Path


_EXAMPLES_ROOT = Path(__file__).resolve().parents[1] / "examples"
_ADAPTER_GLOBS = (
    "cases/*/cases/*/adapter/*.py",
    "_misc_examples/*.py",
)


def test_direct_algorithm_adapters_implement_required_update() -> None:
    """Every shipped example adapter must close the required propose/update API."""

    missing: list[str] = []
    paths = sorted({path for pattern in _ADAPTER_GLOBS for path in _EXAMPLES_ROOT.glob(pattern)})
    for path in paths:
        tree = ast.parse(path.read_text(encoding="utf-8-sig"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.ClassDef):
                continue
            direct_bases = {ast.unparse(base).rsplit(".", 1)[-1] for base in node.bases}
            if "AlgorithmAdapter" not in direct_bases:
                continue
            methods = {
                item.name
                for item in node.body
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef))
            }
            if "update" not in methods:
                missing.append(f"{path.relative_to(_EXAMPLES_ROOT)}::{node.name}")

    assert not missing, "Example adapters missing required update(): " + ", ".join(missing)
