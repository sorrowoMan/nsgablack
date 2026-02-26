# -*- coding: utf-8 -*-
"""Doctor/Inspector entry for supply_adjustment_nested case."""

from __future__ import annotations

from typing import Optional

from working_nested_optimizer import build_solver as _build_solver
from working_nested_optimizer import main as _main


def build_solver(argv: Optional[list] = None):
    return _build_solver(argv)


def main(argv: Optional[list] = None) -> None:
    _main(argv)


if __name__ == "__main__":
    main()
