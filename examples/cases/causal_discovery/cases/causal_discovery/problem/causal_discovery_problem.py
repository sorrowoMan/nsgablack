"""Causal discovery problems as black-box optimization.

PC-Discovery:    binary adjacency matrix, minimize CI violations + sparsity.
LiNGAM-Discovery: continuous edge weights, minimize non-Gaussian residual dependence.
"""
from __future__ import annotations

import numpy as np

from nsgablack.core.base import BlackBoxProblem


def _adj_from_flat(x_flat: np.ndarray, n_vars: int) -> np.ndarray:
    return np.asarray(x_flat, dtype=float).reshape(n_vars, n_vars)


def _count_cycle_nodes(adj: np.ndarray) -> int:
    """Kahn topological sort: returns number of nodes trapped in cycles."""
    n = adj.shape[0]
    binary = (np.abs(adj) > 1e-8).astype(int)
    np.fill_diagonal(binary, 0)
    in_deg = binary.sum(axis=0).tolist()
    queue = [i for i in range(n) if in_deg[i] == 0]
    visited = 0
    while queue:
        u = queue.pop(0)
        visited += 1
        for v in range(n):
            if binary[u, v]:
                in_deg[v] -= 1
                if in_deg[v] == 0:
                    queue.append(v)
    return n - visited


class PCDiscoveryProblem(BlackBoxProblem):
    """Binary adjacency: minimize BIC score of linear SEM from raw data or correlation matrix."""

    def __init__(self, data: np.ndarray, n_samples: int | None = None, *, sparsity_lambda: float = 1.0):
        data = np.asarray(data, dtype=float)
        if data.ndim == 2 and data.shape[0] != data.shape[1]:
            self._data = data
            self._n_samples, self._n_vars = self._data.shape
        else:
            self._corr = data
            self._n_vars = data.shape[0]
            self._n_samples = int(n_samples or 100)
            self._data = None
        self._sparsity_lambda = float(sparsity_lambda)
        dim = self._n_vars * self._n_vars
        super().__init__(
            name="PCDiscovery",
            dimension=dim,
            bounds=[(0.0, 1.0)] * dim,
            objectives=["minimize"],
        )

    @property
    def n_vars(self) -> int:
        return self._n_vars

    @property
    def n_samples(self) -> int:
        return self._n_samples

    def evaluate(self, candidate: np.ndarray) -> float:
        n = self._n_vars
        adj_flat = np.asarray(candidate, dtype=float).ravel()
        A_bin = (adj_flat.reshape(n, n) >= 0.5).astype(float)
        np.fill_diagonal(A_bin, 0.0)

        if self._data is not None:
            return self._evaluate_from_data(A_bin)

        import numpy.linalg as la

        corr, n_samp = self._corr, self._n_samples
        bic = 0.0
        for j in range(n):
            parents = [i for i in range(n) if A_bin[i, j] > 0.5]
            if not parents:
                bic += n_samp * np.log(max(corr[j, j], 1e-12))
                continue
            C_pp = corr[np.ix_(parents, parents)]
            c_pj = corr[parents, j]
            try:
                beta = la.solve(C_pp + np.eye(len(parents)) * 1e-10, c_pj)
            except la.LinAlgError:
                beta = la.lstsq(C_pp + np.eye(len(parents)) * 1e-10, c_pj, rcond=None)[0]
            resid_var = corr[j, j] - np.dot(c_pj, beta)
            resid_var = max(resid_var, 1e-12)
            bic += n_samp * np.log(resid_var)

        n_edges = int(A_bin.sum())
        bic += np.log(n_samp) * n_edges * self._sparsity_lambda
        return float(bic)

    def _evaluate_from_data(self, A_bin: np.ndarray) -> float:
        n, data = self._n_vars, self._data
        n_samp = self._n_samples
        import numpy.linalg as la

        bic = 0.0
        for j in range(n):
            parents = [i for i in range(n) if A_bin[i, j] > 0.5]
            y = data[:, j].copy()
            if not parents:
                resid_var = np.var(y)
                bic += n_samp * np.log(max(resid_var, 1e-12))
                continue
            X = data[:, parents]
            try:
                beta = la.lstsq(X, y, rcond=None)[0]
            except la.LinAlgError:
                bic += n_samp * np.log(max(np.var(y), 1e-12))
                continue
            resid = y - X @ beta
            resid_var = float(np.mean(resid ** 2))
            bic += n_samp * np.log(max(resid_var, 1e-12))

        n_edges = int(A_bin.sum())
        bic += np.log(n_samp) * n_edges * self._sparsity_lambda
        return float(bic)

    def evaluate_constraints(self, candidate: np.ndarray) -> np.ndarray:
        adj = _adj_from_flat(candidate, self._n_vars)
        cycles = _count_cycle_nodes(adj)
        return np.array([float(cycles)], dtype=float)


class LiNGAMDiscoveryProblem(BlackBoxProblem):
    """Continuous edge weights: minimize residual MSE + non-Gaussian dependence + sparsity."""

    def __init__(self, data: np.ndarray, *, sparsity_lambda: float = 0.1, weight_bounds: float = 2.0):
        self._data = np.asarray(data, dtype=float)
        self._n_samples, self._n_vars = self._data.shape
        self._sparsity_lambda = float(sparsity_lambda)
        self._wb = float(weight_bounds)
        dim = self._n_vars * self._n_vars
        super().__init__(
            name="LiNGAMDiscovery",
            dimension=dim,
            bounds=[(-self._wb, self._wb)] * dim,
            objectives=["minimize"],
        )

    @property
    def n_vars(self) -> int:
        return self._n_vars

    @property
    def n_samples(self) -> int:
        return self._n_samples

    def evaluate(self, candidate: np.ndarray) -> float:
        n, data = self._n_vars, self._data
        adj_flat = np.asarray(candidate, dtype=float).ravel()
        W = adj_flat.reshape(n, n).copy()
        np.fill_diagonal(W, 0.0)

        residuals = data.copy().astype(float)
        for j in range(n):
            for i in range(n):
                residuals[:, j] -= W[i, j] * data[:, i]

        mse_sum = float(np.mean(residuals ** 2))

        dependence = 0.0
        for j in range(n):
            for k in range(j + 1, n):
                rj = residuals[:, j]; rj = rj - rj.mean()
                rk = residuals[:, k]; rk = rk - rk.mean()
                denom = np.sqrt(np.dot(rj, rj) * np.dot(rk, rk))
                if denom > 1e-12:
                    corr = np.dot(rj, rk) / denom
                else:
                    corr = 0.0
                dependence += abs(corr)

        l1 = np.abs(W).sum()
        return float(mse_sum + 0.5 * dependence + self._sparsity_lambda * l1)

    def evaluate_constraints(self, candidate: np.ndarray) -> np.ndarray:
        adj = _adj_from_flat(candidate, self._n_vars)
        cycles = _count_cycle_nodes(adj)
        return np.array([float(cycles)], dtype=float)
