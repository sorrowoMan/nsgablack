# -*- coding: utf-8 -*-
"""Compatibility module for legacy imports.

Real assembly now lives in `build_solver.py`.
"""

from __future__ import annotations

from build_solver import (
    _build_solver_from_args,
    build_multi_agent_solver,
    build_solver,
    cli_main,
    main,
    run_multi_agent,
    run_nsga2,
)

__all__ = [
    "run_nsga2",
    "build_multi_agent_solver",
    "run_multi_agent",
    "_build_solver_from_args",
    "build_solver",
    "main",
    "cli_main",
]

