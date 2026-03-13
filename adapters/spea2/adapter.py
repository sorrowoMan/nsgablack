"""
SPEA2 adapter.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np

from ..nsga2 import NSGA2Adapter, NSGA2Config


@dataclass
class SPEA2Config(NSGA2Config):
    archive_size: int = 80
    k_nearest: int = 1


class SPEA2Adapter(NSGA2Adapter):
    context_requires = ()
    context_provides = ()
    context_mutates = ()
    context_cache = ()
    context_notes = "SPEA2 adapter using strength + density fitness for environmental selection."
    state_recovery_level = "L2"
    state_recovery_notes = "Inherits NSGA-II population snapshot roundtrip and SPEA2 selection parameters."

    def __init__(
        self,
        config: Optional[SPEA2Config] = None,
        name: str = "spea2",
        priority: int = 0,
        **config_kwargs,
    ) -> None:
        resolved = self.resolve_config(
            config=config,
            config_cls=SPEA2Config,
            config_kwargs=config_kwargs,
            adapter_name="SPEA2Adapter",
        )
        super().__init__(config=resolved, name=name, priority=priority)
        self.config = self.cfg
        self.cfg: SPEA2Config = config or SPEA2Config()

    def _environmental_select(self, objectives: np.ndarray, violations: np.ndarray, n_keep: int) -> np.ndarray:
        obj = np.asarray(objectives, dtype=float)
        vio = np.asarray(violations, dtype=float).reshape(-1)
        if obj.ndim == 1:
            obj = obj.reshape(-1, 1)
        n = obj.shape[0]
        if n <= n_keep:
            return np.arange(n, dtype=int)

        feasible = vio <= 1e-10
        fit = self._spea2_fitness(obj)
        # infeasible penalty so feasible set dominates selection order.
        fit = fit + (1e6 * np.maximum(vio, 0.0))

        selected = np.where((fit < 1.0) & feasible)[0].tolist()
        if len(selected) < n_keep:
            rest = [i for i in np.argsort(fit).tolist() if i not in selected]
            selected.extend(rest[: (n_keep - len(selected))])
            return np.asarray(selected[:n_keep], dtype=int)
        if len(selected) == n_keep:
            return np.asarray(selected, dtype=int)

        # Truncation by nearest-neighbor distance (keep sparse archive).
        selected_arr = np.asarray(selected, dtype=int)
        while selected_arr.size > n_keep:
            dist = self._pairwise_dist(obj[selected_arr], obj[selected_arr])
            np.fill_diagonal(dist, np.inf)
            min_dist = np.min(dist, axis=1)
            drop = int(np.argmin(min_dist))
            selected_arr = np.delete(selected_arr, drop)
        return selected_arr

    def _spea2_fitness(self, objectives: np.ndarray) -> np.ndarray:
        n = objectives.shape[0]
        dominate = np.zeros((n, n), dtype=bool)
        for i in range(n):
            ai = objectives[i]
            le = np.all(ai <= objectives, axis=1)
            lt = np.any(ai < objectives, axis=1)
            dominate[i] = le & lt
            dominate[i, i] = False
        strength = np.sum(dominate, axis=1).astype(float)
        raw = np.zeros(n, dtype=float)
        for i in range(n):
            dominators = np.where(dominate[:, i])[0]
            if dominators.size:
                raw[i] = float(np.sum(strength[dominators]))

        dist = self._pairwise_dist(objectives, objectives)
        np.fill_diagonal(dist, np.inf)
        k = int(max(1, min(n - 1, self.cfg.k_nearest)))
        kth = np.partition(dist, k - 1, axis=1)[:, k - 1]
        density = 1.0 / (kth + 2.0)
        return raw + density

    def _pairwise_dist(self, a: np.ndarray, b: np.ndarray) -> np.ndarray:
        aa = np.sum(a * a, axis=1, keepdims=True)
        bb = np.sum(b * b, axis=1, keepdims=True).T
        sq = np.maximum(aa + bb - (2.0 * (a @ b.T)), 0.0)
        return np.sqrt(sq)
