"""
Clustering problem: minimize within-cluster SSE given k centroids.

Representation: flat centroid vector [c0_x, c0_y, c1_x, c1_y, ..., c_{k-1}_x, c_{k-1}_y].
"""

from __future__ import annotations

import numpy as np
from nsgablack.core.base import BlackBoxProblem


class ClusteringProblem(BlackBoxProblem):
    """Minimize within-cluster sum of squared errors.

    The candidate vector encodes k centroid positions.
    SSE is computed by assigning each data point to its nearest centroid.
    """

    def __init__(
        self,
        data: np.ndarray,
        k: int,
        *,
        name: str = "clustering",
    ):
        self.data = np.asarray(data, dtype=float)
        self.n_samples, self.n_features = self.data.shape
        self.k = int(k)
        if self.k < 2:
            raise ValueError("k must be >= 2")
        dim = self.k * self.n_features
        mins = self.data.min(axis=0)
        maxs = self.data.max(axis=0)
        super().__init__(
            dimension=dim,
            objectives=["minimize"],
            bounds=[(float(mins[i % self.n_features]), float(maxs[i % self.n_features])) for i in range(dim)],
            name=name,
        )

    def evaluate(self, candidate: np.ndarray) -> float:
        centroids = np.asarray(candidate, dtype=float).reshape(self.k, self.n_features)
        # (n, k, d) broadcasting for distances
        diff = self.data[:, np.newaxis, :] - centroids[np.newaxis, :, :]  # (n, k, d)
        dist_sq = np.sum(diff * diff, axis=2)  # (n, k)
        assignments = np.argmin(dist_sq, axis=1)  # (n,)
        # SSE
        sse = 0.0
        for c in range(self.k):
            mask = assignments == c
            if mask.sum() > 0:
                sse += np.sum(dist_sq[mask, c])
        return sse

    def get_assignments(self, x: np.ndarray) -> np.ndarray:
        centroids = np.asarray(x, dtype=float).reshape(self.k, self.n_features)
        diff = self.data[:, np.newaxis, :] - centroids[np.newaxis, :, :]
        return np.argmin(np.sum(diff * diff, axis=2), axis=1)

    def get_centroids(self, x: np.ndarray) -> np.ndarray:
        return np.asarray(x, dtype=float).reshape(self.k, self.n_features)
