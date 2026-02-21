"""Simple structure checks for the representation package."""

from __future__ import annotations

import importlib.util
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _check_representation_files() -> bool:
    rep_dir = PROJECT_ROOT / "representation"
    legacy_rep_dir = PROJECT_ROOT / "utils" / "representation"

    checks = [
        rep_dir.exists(),
        (rep_dir / "__init__.py").exists(),
        (rep_dir / "base.py").exists(),
        (rep_dir / "integer.py").exists(),
    ]

    # Legacy path is optional; keep this as soft-compat info only.
    if legacy_rep_dir.exists():
        checks.append((legacy_rep_dir / "__init__.py").exists())

    return all(checks)


def _check_representation_content() -> bool:
    init_file = PROJECT_ROOT / "representation" / "__init__.py"
    spec = importlib.util.spec_from_file_location("representation", init_file)
    return bool(spec and spec.loader)


def test_representation_files() -> None:
    assert _check_representation_files()


def test_representation_content() -> None:
    assert _check_representation_content()
