# -*- coding: utf-8 -*-
"""Doctor/Inspector standard entry for production_scheduling case.

This file keeps scaffold compatibility:
- provides build_solver() at project root
- delegates real logic to working_integrated_optimizer.py
"""

from __future__ import annotations

from typing import Optional

from working_integrated_optimizer import build_solver as _build_solver
from working_integrated_optimizer import main as _main


def build_solver(argv: Optional[list] = None):
    """Delegate to the case's real builder."""
    return _build_solver(argv)


def main(argv: Optional[list] = None) -> None:
    _main(argv)


if __name__ == "__main__":
    main()

