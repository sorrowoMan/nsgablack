"""Local bootstrap helpers for examples under the nsgablack repo.

These examples may live inside the `nsgablack/` package directory itself.
When executed directly, Python cannot import `nsgablack` unless the *parent*
directory of the package is on sys.path.
"""

from __future__ import annotations

import sys
from pathlib import Path


def ensure_nsgablack_importable(start: Path | None = None) -> None:
    """Ensure `import nsgablack` works for a script located inside this repo."""

    start = (start or Path(__file__)).resolve()
    cur = start
    for _ in range(10):
        # Repo root (package dir) contains pyproject.toml in this layout.
        if (cur / "pyproject.toml").exists() and (cur / "__init__.py").exists():
            pkg_dir = cur
            parent = pkg_dir.parent
            if str(parent) not in sys.path:
                sys.path.insert(0, str(parent))
            return
        cur = cur.parent

