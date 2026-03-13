# -*- coding: utf-8 -*-
"""Compatibility wrapper for historical entry script.

New standard structure:
- stable entry: build_solver.py
- assembly control-plane: solver/assembly.py
- CLI entry: solver/run_case.py
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

from build_solver import (  # noqa: E402
    _build_solver_from_args as _assembly_build_solver_from_args,
    build_multi_agent_solver as _assembly_build_multi_agent_solver,
    build_solver as _assembly_build_solver,
    cli_main as _assembly_cli_main,
    main as _assembly_main,
    run_multi_agent as _assembly_run_multi_agent,
    run_nsga2 as _assembly_run_nsga2,
)


def run_nsga2(problem, args):
    return _assembly_run_nsga2(problem, args)


def build_multi_agent_solver(problem, args):
    return _assembly_build_multi_agent_solver(problem, args, case_root=_THIS_DIR)


def run_multi_agent(problem, args):
    return _assembly_run_multi_agent(problem, args, case_root=_THIS_DIR)


def _build_solver_from_args(args):
    return _assembly_build_solver_from_args(args, case_root=_THIS_DIR)


def build_solver(argv: Optional[list] = None):
    return _assembly_build_solver(argv, case_root=_THIS_DIR)


def main(args=None):
    return _assembly_main(args, case_root=_THIS_DIR)


if __name__ == "__main__":
    raise SystemExit(_assembly_cli_main(case_root=_THIS_DIR))
