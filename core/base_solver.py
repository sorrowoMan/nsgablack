"""Deprecated module (transition).

The project converges on:
- `core/solver.py` (NSGA-II baseline)
- `core/blank_solver.py`
- `core/composable_solver.py`
- `core/adapters/`

The old `BaseSolver` abstraction is kept only in legacy for archaeology.
Use `core/config.py` for the stable `SolverConfig`.
"""

from __future__ import annotations

import warnings

from .config import OptimizationResult, SolverConfig

__all__ = ["SolverConfig", "OptimizationResult", "BaseSolver"]


def __getattr__(name):  # pragma: no cover
    if name == "BaseSolver":
        warnings.warn(
            "nsgablack.core.base_solver.BaseSolver is deprecated; "
            "use BlackBoxSolverNSGAII / BlankSolverBase / ComposableSolver + adapters.",
            DeprecationWarning,
            stacklevel=2,
        )
        from ..deprecated.legacy.core.base_solver import BaseSolver  # type: ignore

        return BaseSolver
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")

