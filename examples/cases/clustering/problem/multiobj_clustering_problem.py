"""Multi-objective clustering: simultaneously minimize intra-SSE and maximize inter-centroid separation."""
from __future__ import annotations

import numpy as np
from nsgablack.core.base import BlackBoxProblem


class MultiObjectiveClusteringProblem(BlackBoxProblem):
    """Two objectives: (1) minimize intra-cluster SSE, (2) maximize inter-centroid distance."""

    def __init__(self, data: np.ndarray, k: int, *, name: str = "multiobj_clustering"):
        self.data = np.asarray(data, dtype=float)
        self.n_samples, self.n_features = self.data.shape
        self.k = int(k)
        dim = self.k * self.n_features
        mins = self.data.min(axis=0)
        maxs = self.data.max(axis=0)
        super().__init__(
            dimension=dim,
            objectives=["minimize", "maximize"],
            bounds=[(float(mins[i % self.n_features]), float(maxs[i % self.n_features])) for i in range(dim)],
            name=name,
        )

    def evaluate(self, x: np.ndarray) -> np.ndarray:
        centroids = np.asarray(x, dtype=float).reshape(self.k, self.n_features)
        diff = self.data[:, np.newaxis, :] - centroids[np.newaxis, :, :]
        dist_sq = np.sum(diff * diff, axis=2)
        assignments = np.argmin(dist_sq, axis=1)

        # Objective 1: intra-cluster SSE (minimize)
        intra_sse = 0.0
        for c in range(self.k):
            mask = assignments == c
            if mask.sum() > 0:
                intra_sse += np.sum(dist_sq[mask, c])

        # Objective 2: inter-centroid separation (maximize)
        inter_dist = 0.0
        count = 0
        for i in range(self.k):
            for j in range(i + 1, self.k):
                inter_dist += np.sqrt(np.sum((centroids[i] - centroids[j]) ** 2))
                count += 1
        inter_dist = inter_dist / max(count, 1)

        return np.array([float(intra_sse), float(-inter_dist)])  # negate because maximize

    def get_assignments(self, x: np.ndarray) -> np.ndarray:
        centroids = np.asarray(x, dtype=float).reshape(self.k, self.n_features)
        diff = self.data[:, np.newaxis, :] - centroids[np.newaxis, :, :]
        return np.argmin(np.sum(diff * diff, axis=2), axis=1)

    def get_centroids(self, x: np.ndarray) -> np.ndarray:
        return np.asarray(x, dtype=float).reshape(self.k, self.n_features)
