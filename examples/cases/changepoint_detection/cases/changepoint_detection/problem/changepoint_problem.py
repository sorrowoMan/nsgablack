"""Changepoint detection: find structural breaks in a time series.

nsgablack searches for optimal changepoint positions.
Bias layer provides sparsity penalty (fewer changepoints = simpler model).
"""

from __future__ import annotations

import numpy as np
from nsgablack.core.base import BlackBoxProblem


class ChangepointProblem(BlackBoxProblem):
    """Minimize segmented residual sum of squares.

    Candidate encodes sorted changepoint positions [cp1, cp2, ..., cp_kmax].
    """

    def __init__(self, signal: np.ndarray, max_changepoints: int = 3):
        self.signal = np.asarray(signal, dtype=float)
        self.n = len(self.signal)
        self.max_cp = int(max_changepoints)
        super().__init__(
            dimension=self.max_cp,
            objectives=["minimize"],
            bounds=[(5.0, float(self.n - 5))] * self.max_cp,
            name="changepoint",
        )

    def evaluate(self, candidate: np.ndarray) -> float:
        cps = np.sort(np.clip(np.asarray(candidate, dtype=int), 5, self.n - 5))
        cps = np.unique(cps)
        if len(cps) < 1:
            return 1e10
        total_cost = 0.0
        prev = 0
        for cp in cps:
            seg = self.signal[prev:cp]
            if len(seg) > 2:
                total_cost += float(np.sum((seg - seg.mean()) ** 2))
            prev = cp
        seg = self.signal[prev:]
        if len(seg) > 2:
            total_cost += float(np.sum((seg - seg.mean()) ** 2))
        return float(total_cost / self.n)

    def get_changepoints(self, x: np.ndarray) -> np.ndarray:
        cps = np.sort(np.clip(np.asarray(x, dtype=int), 5, self.n - 5))
        return np.unique(cps)
