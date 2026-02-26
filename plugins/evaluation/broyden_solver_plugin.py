from __future__ import annotations

from typing import Optional, Sequence

import numpy as np
from scipy import optimize

from .numerical_solver_base import (
    JacobianFn,
    NumericalSolveResult,
    NumericalSolverConfig,
    NumericalSolverPlugin,
    ResidualFn,
)


class BroydenSolverPlugin(NumericalSolverPlugin):
    """Broyden nonlinear solver plugin using scipy.optimize.broyden1."""

    context_requires = NumericalSolverPlugin.context_requires
    context_provides = NumericalSolverPlugin.context_provides
    context_mutates = NumericalSolverPlugin.context_mutates
    context_cache = NumericalSolverPlugin.context_cache
    context_notes = NumericalSolverPlugin.context_notes

    def __init__(self, name: str = "broyden_solver", *, config: Optional[NumericalSolverConfig] = None) -> None:
        super().__init__(name=name, config=config, priority=55)

    def solve_backend(
        self,
        residual: ResidualFn,
        x0: np.ndarray,
        jacobian: Optional[JacobianFn] = None,
    ) -> NumericalSolveResult:
        _ = jacobian
        history: Sequence[np.ndarray] = []
        iterations = 0

        def _callback(xk: np.ndarray, fk: np.ndarray) -> None:
            nonlocal iterations, history
            iterations += 1
            history = (*history, np.asarray(fk, dtype=float).reshape(-1))

        solution = optimize.broyden1(
            residual,
            xin=np.asarray(x0, dtype=float).reshape(-1),
            iter=int(self.cfg.max_iter),
            f_tol=float(self.cfg.tol),
            callback=_callback,
        )
        sol = np.asarray(solution, dtype=float).reshape(-1)
        residual_val = np.asarray(residual(sol), dtype=float).reshape(-1)
        return NumericalSolveResult(
            solution=sol,
            residual_norm=float(np.linalg.norm(residual_val)),
            iterations=int(iterations),
            success=bool(np.linalg.norm(residual_val) <= float(self.cfg.tol) * 10.0),
            method="broyden1",
            message="",
        )

