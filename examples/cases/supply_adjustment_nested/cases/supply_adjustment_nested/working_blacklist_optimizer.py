# -*- coding: utf-8 -*-
"""Compatibility wrapper for the historical L0 blacklist optimizer entry.

The formal scaffold entry now lives in `solver/blacklist_assembly.py`.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional

_THIS_DIR = Path(__file__).resolve().parent
if str(_THIS_DIR) not in sys.path:
    sys.path.insert(0, str(_THIS_DIR))

from _bootstrap import ensure_nsgablack_importable  # noqa: E402

ensure_nsgablack_importable(Path(__file__))

from solver.blacklist_assembly import (  # noqa: E402
    _build_solver,
    build_parser,
    build_solver,
    main,
)

__all__ = [
    "build_parser",
    "_build_solver",
    "build_solver",
    "main",
]


if __name__ == "__main__":
    main()
