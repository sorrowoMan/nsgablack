"""Local bootstrap helpers for examples under the nsgablack repo."""

from __future__ import annotations

import sys
from pathlib import Path


def ensure_nsgablack_importable(start: Path | None = None) -> None:
    """Ensure `import nsgablack` works for scripts executed inside repo."""
    start = (start or Path(__file__)).resolve()
    cur = start
    for _ in range(10):
        if (cur / "pyproject.toml").exists() and (cur / "__init__.py").exists():
            pkg_dir = cur
            parent = pkg_dir.parent
            if str(parent) not in sys.path:
                sys.path.insert(0, str(parent))
            return
        cur = cur.parent
