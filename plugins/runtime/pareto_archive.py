"""
Pareto archive plugin.

This plugin is intentionally solver-base-agnostic. It can work with:
- evolutionary solvers (reading solver.population/objectives/constraint_violations)
- MOEADAdapter (reading solver.adapter.get_population())
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional, Tuple

import numpy as np

from ..base import Plugin


@dataclass
class ParetoArchiveConfig:
    keep_infeasible: bool = False
    max_size: Optional[int] = None


class ParetoArchivePlugin(Plugin):
    is_algorithmic = True
    context_requires = ()
    context_provides = ()
    context_mutates = ()
    context_cache = ()
    context_notes = (
        "Reads solver population/objectives/violations or adapter population; "
        "updates solver-level pareto_solutions/pareto_objectives."
    )
    """Maintain a global non-dominated archive."""

    provides_metrics = {"pareto_archive_size"}

    def __init__(
        self,
        name: str = "pareto_archive",
        *,
        config: Optional[ParetoArchiveConfig] = None,
    ) -> None:
        super().__init__(name=name)
        self.cfg = config or ParetoArchiveConfig()
        self.archive_X: Optional[np.ndarray] = None
        self.archive_F: Optional[np.ndarray] = None
        self.archive_V: Optional[np.ndarray] = None

    def on_generation_end(self, generation: int):
        solver = self.solver
        if solver is None:
            return None

        X, F, V = self._get_population(solver)
        if X.size == 0:
            return None

        self._update_archive(X, F, V)
        try:
            setattr(solver, "pareto_solutions", None if self.archive_X is None else np.asarray(self.archive_X))
            setattr(solver, "pareto_objectives", None if self.archive_F is None else np.asarray(self.archive_F))
        except Exception:
            pass
        return None

    # ------------------------------------------------------------------
    def _get_population(self, solver: Any) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        adapter = getattr(solver, "adapter", None)
        if adapter is not None and getattr(adapter, "get_population", None) is not None:
            try:
                X, F, V = adapter.get_population()
                return np.asarray(X, dtype=float), np.asarray(F, dtype=float), np.asarray(V, dtype=float).reshape(-1)
            except Exception:
                pass

        X = np.asarray(getattr(solver, "population", np.zeros((0,))), dtype=float)
        F = np.asarray(getattr(solver, "objectives", np.zeros((0,))), dtype=float)
        V = np.asarray(getattr(solver, "constraint_violations", np.zeros((0,))), dtype=float).reshape(-1)
        if X.ndim == 1:
            X = X.reshape(0, 0) if X.size == 0 else X.reshape(1, -1)
        if F.ndim == 1:
            F = F.reshape(-1, 1) if F.size > 0 else F.reshape(0, 0)
        return X, F, V

    def _update_archive(self, X: np.ndarray, F: np.ndarray, V: np.ndarray) -> None:
        if self.archive_X is None:
            self.archive_X = np.asarray(X, dtype=float)
            self.archive_F = np.asarray(F, dtype=float)
            self.archive_V = np.asarray(V, dtype=float).reshape(-1)
        else:
            self.archive_X = np.vstack([self.archive_X, np.asarray(X, dtype=float)])
            self.archive_F = np.vstack([self.archive_F, np.asarray(F, dtype=float)])
            self.archive_V = np.concatenate([self.archive_V, np.asarray(V, dtype=float).reshape(-1)])

        # filter infeasible unless configured otherwise
        if not self.cfg.keep_infeasible:
            feas = (self.archive_V <= 0.0)
            self.archive_X = self.archive_X[feas]
            self.archive_F = self.archive_F[feas]
            self.archive_V = self.archive_V[feas]

        if self.archive_F.size == 0:
            return

        nd = self._nondominated_mask(self.archive_F)
        self.archive_X = self.archive_X[nd]
        self.archive_F = self.archive_F[nd]
        self.archive_V = self.archive_V[nd]

        if self.cfg.max_size is not None and self.archive_F.shape[0] > int(self.cfg.max_size):
            # simple downsample: keep evenly spaced by index
            k = int(self.cfg.max_size)
            idx = np.linspace(0, self.archive_F.shape[0] - 1, num=k).astype(int)
            self.archive_X = self.archive_X[idx]
            self.archive_F = self.archive_F[idx]
            self.archive_V = self.archive_V[idx]

    @staticmethod
    def _nondominated_mask(F: np.ndarray) -> np.ndarray:
        F = np.asarray(F, dtype=float)
        n = int(F.shape[0])
        dominated = np.zeros(n, dtype=bool)
        for i in range(n):
            if dominated[i]:
                continue
            fi = F[i]
            for j in range(n):
                if i == j or dominated[i]:
                    continue
                fj = F[j]
                if np.all(fj <= fi) and np.any(fj < fi):
                    dominated[i] = True
        return ~dominated

