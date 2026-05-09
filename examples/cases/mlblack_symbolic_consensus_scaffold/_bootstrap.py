from __future__ import annotations

import sys
from pathlib import Path


def ensure_nsgablack_importable(start: Path | None = None) -> None:
    start = (start or Path(__file__)).resolve()
    cur = start
    for _ in range(10):
        if (cur / "pyproject.toml").exists() and (cur / "__init__.py").exists():
            parent = cur.parent
            if str(parent) not in sys.path:
                sys.path.insert(0, str(parent))
            return
        cur = cur.parent

