from __future__ import annotations

import ast
from pathlib import Path


def test_nonempty_requires_metrics_has_explicit_fallback_or_policy() -> None:
    bias_root = Path(__file__).resolve().parents[1] / "bias"
    missing: list[str] = []

    for path in sorted(bias_root.rglob("*.py")):
        if path.name == "__init__.py":
            continue
        source = path.read_text(encoding="utf-8", errors="ignore")
        try:
            tree = ast.parse(source)
        except SyntaxError:
            continue

        for node in tree.body:
            if not isinstance(node, ast.ClassDef):
                continue
            has_nonempty_requires = False
            has_policy = False
            has_fallback = False
            for item in node.body:
                if not isinstance(item, ast.Assign):
                    continue
                for target in item.targets:
                    if not isinstance(target, ast.Name):
                        continue
                    if target.id == "requires_metrics":
                        value = item.value
                        if isinstance(value, (ast.Tuple, ast.List)):
                            has_nonempty_requires = len(value.elts) > 0
                        else:
                            has_nonempty_requires = True
                    elif target.id == "missing_metrics_policy":
                        has_policy = True
                    elif target.id == "metrics_fallback":
                        has_fallback = True
            if has_nonempty_requires and not (has_policy or has_fallback):
                missing.append(f"{path.relative_to(bias_root.parent)}::{node.name}")

    assert not missing, "classes with requires_metrics must declare metrics_fallback or missing_metrics_policy:\n" + "\n".join(missing)
