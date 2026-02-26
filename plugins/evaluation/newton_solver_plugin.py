from __future__ import annotations

from typing import Any, Dict, Optional

import numpy as np
from scipy import optimize

from .numerical_solver_base import (
    JacobianFn,
    NumericalSolveResult,
    NumericalSolverConfig,
    NumericalSolverPlugin,
    ResidualFn,
)


class NewtonSolverPlugin(NumericalSolverPlugin):
    """Newton-style nonlinear solver plugin using scipy.optimize.root (hybr)."""

    context_requires = NumericalSolverPlugin.context_requires
    context_provides = NumericalSolverPlugin.context_provides
    context_mutates = NumericalSolverPlugin.context_mutates
    context_cache = NumericalSolverPlugin.context_cache
    context_notes = NumericalSolverPlugin.context_notes

    def __init__(self, name: str = "newton_solver", *, config: Optional[NumericalSolverConfig] = None) -> None:
        super().__init__(name=name, config=config, priority=60)

    def solve_backend(
        self,
        residual: ResidualFn,
        x0: np.ndarray,
        jacobian: Optional[JacobianFn] = None,
    ) -> NumericalSolveResult:
        kwargs: Dict[str, Any] = {"tol": float(self.cfg.tol)}
        if jacobian is not None:
            kwargs["jac"] = jacobian
        out = optimize.root(residual, x0, method="hybr", options={"maxfev": int(self.cfg.max_iter)}, **kwargs)
        solution = np.asarray(out.x, dtype=float).reshape(-1)
        residual_val = np.asarray(residual(solution), dtype=float).reshape(-1)
        return NumericalSolveResult(
            solution=solution,
            residual_norm=float(np.linalg.norm(residual_val)),
            iterations=int(getattr(out, "nfev", 0)),
            success=bool(getattr(out, "success", False)),
            method="newton_hybr",
            message=str(getattr(out, "message", "")),
        )

