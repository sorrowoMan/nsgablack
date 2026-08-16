# -*- coding: utf-8 -*-
"""Doctor/Inspector entry for supply_adjustment_nested case.

This file intentionally stays thin: project doctor, catalog and examples all
enter through `build_solver`, while real L1/L2 assembly lives in
`solver/assembly.py`.
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

from solver.assembly import build_solver as _build_solver  # noqa: E402


def build_solver(argv: Optional[list] = None, *, resource_context=None, component_overrides=None):
    del component_overrides
    return _build_solver(argv, resource_context=resource_context)
