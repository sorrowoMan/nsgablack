"""RANSAC: search inlier mask via DE."""
import numpy as np
from nsgablack.core.base import BlackBoxProblem

class RANSACProblem(BlackBoxProblem):
    def __init__(self, X, y):
        self._X = np.asarray(X, dtype=float); self._y = np.asarray(y, dtype=float)
        self.n_samples = len(y)
        super().__init__(dimension=self.n_samples, objectives=["minimize"],
                         bounds=[(0.0, 1.0)] * self.n_samples, name="ransac")

    def evaluate(self, candidate):
        mask = np.asarray(candidate, dtype=float) > 0.5
        if mask.sum() < 20: return 1e10
        try:
            w = np.linalg.lstsq(self._X[mask], self._y[mask], rcond=None)[0]
            return float(np.sum((self._y[mask] - self._X[mask] @ w) ** 2))
        except Exception: return 1e10
