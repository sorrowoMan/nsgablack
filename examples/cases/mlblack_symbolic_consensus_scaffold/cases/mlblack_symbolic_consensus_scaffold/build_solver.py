# -*- coding: utf-8 -*-
"""Thin entrypoint for the mlblack symbolic consensus scaffold."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional

_THIS_DIR = Path(__file__).resolve().parent
if str(_THIS_DIR) not in sys.path:
    sys.path.insert(0, str(_THIS_DIR))

from _bootstrap import ensure_nsgablack_importable  # noqa: E402

ensure_nsgablack_importable(Path(__file__))

from case_scaffold.config.parser import build_parser  # noqa: E402
from case_scaffold.orchestration.solver import build_solver_from_args  # noqa: E402


def build_solver(argv: Optional[list[str]] = None, *, resource_context=None, component_overrides=None):
    del component_overrides
    args = build_parser().parse_args(argv if argv is not None else [])
    if bool(args.check):
        args.no_logs = True
    solver = build_solver_from_args(args)
    solver.set_resource_context(resource_context)
    return solver
