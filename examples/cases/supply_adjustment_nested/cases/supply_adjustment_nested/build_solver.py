# -*- coding: utf-8 -*-
"""Doctor/Inspector entry for supply_adjustment_nested case.

This file intentionally stays thin: project doctor, catalog and examples all
enter through `build_solver`, while real L1/L2 assembly lives in
`solver/assembly.py`.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from solver.assembly import build_solver as _build_solver  # noqa: E402


def build_solver(argv: Optional[list] = None, *, resource_context=None, component_overrides=None):
    overrides = dict(component_overrides or {})
    configured_argv = overrides.pop("argv", argv)
    solver = _build_solver(configured_argv, resource_context=resource_context)
    from nsgablack.project import apply_solver_component_overrides

    apply_solver_component_overrides(solver, overrides)
    return solver
