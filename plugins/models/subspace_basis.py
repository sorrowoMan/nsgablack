"""
Subspace basis plugin (random / PCA).

Provides context["subspace_basis"] for subspace trust-region adapters.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

import numpy as np

from ..base import Plugin
from ...utils.context.context_keys import KEY_SUBSPACE_BASIS


@dataclass
class SubspaceBasisConfig:
    method: str = "pca"  # "pca", "svd", "sparse_pca", "cluster", "random"
    subspace_dim: int = 8
    min_samples: int = 32
    update_every: int = 5
    random_seed: Optional[int] = None


class SubspaceBasisPlugin(Plugin):
    context_requires = ()
    context_provides = (KEY_SUBSPACE_BASIS,)
    context_mutates = (KEY_SUBSPACE_BASIS,)
    context_cache = ()
    context_notes = "Updates subspace basis from population samples."
    """
    Maintains a subspace basis from recent population samples.
    """

    def __init__(
        self,
        name: str = "subspace_basis",
        *,
        config: Optional[SubspaceBasisConfig] = None,
    ) -> None:
        super().__init__(name=name)
        self.cfg = config or SubspaceBasisConfig()
        self._rng = np.random.default_rng(self.cfg.random_seed)
        self._basis: Optional[np.ndarray] = None
        self._steps = 0

    def on_generation_end(self, generation: int):
        solver = self.solver
        if solver is None:
            return None
        self._steps += 1
        if (self._steps % max(1, int(self.cfg.update_every))) != 0:
            return None
        pop, _, _ = self.resolve_population_snapshot(solver)
        if pop is None or len(pop) == 0:
            return None
        X = np.asarray(pop, dtype=float)
        if X.ndim != 2 or X.shape[0] < int(self.cfg.min_samples):
            return None
        self._basis = self._build_basis(X)
        return None

    def on_context_build(self, context: Dict[str, Any]) -> Dict[str, Any]:
        if self._basis is not None:
            context[KEY_SUBSPACE_BASIS] = self._basis
        return context

    def _build_basis(self, X: np.ndarray) -> np.ndarray:
        dim = int(X.shape[1])
        k = min(max(1, int(self.cfg.subspace_dim)), dim)
        method = str(self.cfg.method).lower().strip()
        if method == "random":
            mat = self._rng.normal(size=(dim, k))
            q, _ = np.linalg.qr(mat)
            return q[:, :k]

        if method == "svd":
            Xc = X - np.mean(X, axis=0, keepdims=True)
            try:
                _, _, vt = np.linalg.svd(Xc, full_matrices=False)
                return vt[:k].T
            except Exception:
                mat = self._rng.normal(size=(dim, k))
                q, _ = np.linalg.qr(mat)
                return q[:, :k]

        if method == "sparse_pca":
            try:
                from sklearn.decomposition import SparsePCA

                spca = SparsePCA(n_components=k, random_state=self.cfg.random_seed)
                spca.fit(X)
                basis = np.asarray(spca.components_, dtype=float).T
                return basis
            except Exception:
                method = "pca"

        if method == "cluster":
            try:
                from sklearn.cluster import KMeans

                n_clusters = min(max(2, k), X.shape[0])
                km = KMeans(n_clusters=n_clusters, random_state=self.cfg.random_seed, n_init=5)
                labels = km.fit_predict(X)
                centers = km.cluster_centers_
                Xc = centers - np.mean(centers, axis=0, keepdims=True)
                _, _, vt = np.linalg.svd(Xc, full_matrices=False)
                return vt[:k].T
            except Exception:
                method = "pca"

        # PCA basis (top-k right singular vectors)
        Xc = X - np.mean(X, axis=0, keepdims=True)
        try:
            _, _, vt = np.linalg.svd(Xc, full_matrices=False)
            basis = vt[:k].T
            return basis
        except Exception:
            mat = self._rng.normal(size=(dim, k))
            q, _ = np.linalg.qr(mat)
            return q[:, :k]

