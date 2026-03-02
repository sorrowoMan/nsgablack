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
        "updates runtime pareto snapshot (pareto_solutions/pareto_objectives)."
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
        self._write_pareto_snapshot(solver)
        return None

    # ------------------------------------------------------------------
    def _get_population(self, solver: Any) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        return self.resolve_population_snapshot(solver)

    def _write_pareto_snapshot(self, solver: Any) -> None:
        setter = getattr(solver, "set_pareto_snapshot", None)
        if callable(setter):
            try:
                setter(self.archive_X, self.archive_F)
                return
            except Exception:
                pass
        runtime = getattr(solver, "runtime", None)
        if runtime is not None and hasattr(runtime, "set_pareto_snapshot"):
            try:
                runtime.set_pareto_snapshot(self.archive_X, self.archive_F)
                return
            except Exception:
                pass
        try:
            for field, value in (
                ("pareto_solutions", None if self.archive_X is None else np.asarray(self.archive_X)),
                ("pareto_objectives", None if self.archive_F is None else np.asarray(self.archive_F)),
            ):
                setattr(solver, field, value)
        except Exception:
            return

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
            # Truncate by crowding distance to preserve front diversity.
            k = int(self.cfg.max_size)
            idx = self._select_by_crowding(self.archive_F, k)
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

    @staticmethod
    def _select_by_crowding(F: np.ndarray, k: int) -> np.ndarray:
        F = np.asarray(F, dtype=float)
        n = int(F.shape[0])
        if k >= n:
            return np.arange(n, dtype=int)
        if n == 0:
            return np.array([], dtype=int)
        if F.ndim == 1:
            F = F.reshape(-1, 1)

        m = int(F.shape[1])
        crowd = np.zeros(n, dtype=float)
        for obj in range(m):
            order = np.argsort(F[:, obj])
            crowd[order[0]] = np.inf
            crowd[order[-1]] = np.inf
            fmin = float(F[order[0], obj])
            fmax = float(F[order[-1], obj])
            denom = fmax - fmin
            if denom <= 1e-12:
                continue
            for i in range(1, n - 1):
                prev_v = float(F[order[i - 1], obj])
                next_v = float(F[order[i + 1], obj])
                crowd[order[i]] += (next_v - prev_v) / denom

        selected = np.argsort(-crowd)[:k]
        return np.sort(selected.astype(int))

