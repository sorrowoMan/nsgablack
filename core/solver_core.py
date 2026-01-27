"""Deprecated module.

`core/solver_core.py` was an experimental "pure" NSGA-II implementation that
never became part of the stable API surface.

Use:
- `core/solver.py` (`BlackBoxSolverNSGAII`) for the stable NSGA-II baseline
- `core/composable_solver.py` + `core/adapters/` for strategy composition
"""

from __future__ import annotations

import warnings

warnings.warn(
    "core.solver_core is deprecated and kept only as an empty stub. "
    "Use core.solver.BlackBoxSolverNSGAII or ComposableSolver + adapters.",
    DeprecationWarning,
    stacklevel=2,
)

__all__ = []

