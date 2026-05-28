"""Kernel SHAP: nsgablack searches SHAP values via coalition-weighted regression.

Given a trained mlblack/sklearn model, nsgablack PatternSearch finds phi
that minimize the Shapley-kernel-weighted reconstruction error over coalitions.
"""

import numpy as np
from nsgablack.core.base import BlackBoxProblem


def _shapley_kernel(n_features: int, coalition_size: int) -> float:
    """Shapley kernel weight for a coalition of given size."""
    if coalition_size == 0 or coalition_size == n_features:
        return 1e6  # large constant for full/empty coalitions
    from math import comb
    return float((n_features - 1) / (comb(n_features, coalition_size) * coalition_size * (n_features - coalition_size)))


class KernelSHAPProblem(BlackBoxProblem):
    """Minimize Shapley-kernel-weighted reconstruction error over m coalitions.

    Candidate phi = [phi_0, phi_1, ..., phi_n_features] — intercept + per-feature contributions.
    """

    def __init__(self, model, X_bg: np.ndarray, x_target: np.ndarray, *, n_coalitions: int = 200):
        self._model = model
        self._X_bg = np.asarray(X_bg, dtype=float)
        self._x_target = np.asarray(x_target, dtype=float)
        self._n_features = len(x_target)
        self._n_coalitions = int(n_coalitions)

        # Pre-sample coalitions and pre-compute kernel weights
        rng = np.random.default_rng(42)
        self._coalitions = rng.integers(0, 2, size=(n_coalitions, self._n_features)).astype(float)
        self._coalition_sizes = self._coalitions.sum(axis=1).astype(int)
        self._weights = np.array([_shapley_kernel(self._n_features, s) for s in self._coalition_sizes])

        # Pre-compute f(h_x(z)) for each coalition — mlblack/sklearn model does the heavy lifting
        self._fz = np.zeros(n_coalitions)
        for i in range(n_coalitions):
            hybrid = self._x_target * self._coalitions[i] + X_bg.mean(axis=0) * (1 - self._coalitions[i])
            self._fz[i] = float(self._model.predict(hybrid.reshape(1, -1))[0])

        bound = max(abs(self._fz.max()), abs(self._fz.min())) * 2.0
        super().__init__(
            dimension=self._n_features + 1,
            objectives=["minimize"],
            bounds=[(-bound, bound)] * (self._n_features + 1),
            name="kernel_shap",
        )

    def evaluate(self, phi: np.ndarray) -> float:
        phi = np.asarray(phi, dtype=float)
        phi_0, phi_feat = phi[0], phi[1:]
        # Weighted reconstruction error over all coalitions
        recon = phi_0 + np.sum(phi_feat * self._coalitions, axis=1)
        error = np.sum(self._weights * (self._fz - recon) ** 2)
        return float(error)

    def get_shap_values(self, phi: np.ndarray) -> np.ndarray:
        return np.asarray(phi[1:], dtype=float)

    def analytical_solution(self) -> np.ndarray:
        """Closed-form WLS solution: (Z^T W Z)^(-1) Z^T W f."""
        Z = np.hstack([np.ones((self._n_coalitions, 1)), self._coalitions])
        W = np.diag(self._weights)
        ZTW = Z.T @ W
        phi = np.linalg.solve(ZTW @ Z, ZTW @ self._fz)
        return phi  # [phi_0, phi_1, ..., phi_n]
