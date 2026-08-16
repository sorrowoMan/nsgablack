"""k-medians: same as k-means but with L1 distance (Manhattan)."""
import numpy as np
from .clustering_problem import ClusteringProblem


class KMediansProblem(ClusteringProblem):
    """Minimize within-cluster sum of L1 distances."""

    def evaluate(self, candidate: np.ndarray) -> float:
        centroids = np.asarray(candidate, dtype=float).reshape(self.k, self.n_features)
        diff = self.data[:, np.newaxis, :] - centroids[np.newaxis, :, :]
        dist_l1 = np.sum(np.abs(diff), axis=2)  # ← only change: L2 → L1
        assignments = np.argmin(dist_l1, axis=1)
        sad = 0.0
        for c in range(self.k):
            mask = assignments == c
            if mask.sum() > 0:
                sad += np.sum(dist_l1[mask, c])
        return sad
