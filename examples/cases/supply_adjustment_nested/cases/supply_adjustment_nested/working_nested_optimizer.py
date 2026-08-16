# -*- coding: utf-8 -*-
"""Compatibility wrapper for the historical nested supply-adjustment entry.

The formal scaffold entry now lives in `solver/assembly.py`. Keep this file
thin so old commands continue to work without duplicating case assembly logic.
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

from solver.assembly import (  # noqa: E402
    _build_solver_from_args,
    build_parser,
    build_solver,
    main,
)

__all__ = [
    "build_parser",
    "_build_solver_from_args",
    "build_solver",
    "main",
]


if __name__ == "__main__":
    main()
