"""
Subspace/low-rank trust-region (CUATRO_PLS-style) adapter.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

import numpy as np

from ..trust_region_base import TrustRegionBaseAdapter


@dataclass
class TrustRegionSubspaceConfig:
    batch_size: int = 16
    initial_radius: float = 0.5
    min_radius: float = 1e-6
    max_radius: float = 2.0
    radius_expand: float = 1.5
    radius_shrink: float = 0.7
    success_tolerance: float = 1e-8
    include_center: bool = True
    subspace_dim: int = 8
    basis_method: str = "random"  # random | pca | svd | sparse_pca | cluster
    min_samples: int = 32
    resample_every: int = 10
    random_seed: Optional[int] = None


class TrustRegionSubspaceAdapter(TrustRegionBaseAdapter):
    """
    Trust-region local search in a low-dimensional subspace.

    Uses a random orthonormal subspace and samples within it.
    """
    context_requires = ("generation",)
    context_provides = ()
    context_mutates = ()
    context_cache = ()
    context_notes = ("Subspace basis is managed internally (random or population-derived).",)

    def __init__(
        self,
        config: Optional[TrustRegionSubspaceConfig] = None,
        name: str = "trust_region_subspace",
        priority: int = 0,
        **config_kwargs,
    ) -> None:
        cfg = self.resolve_config(
            config=config,
            config_cls=TrustRegionSubspaceConfig,
            config_kwargs=config_kwargs,
            adapter_name="TrustRegionSubspaceAdapter",
        )
        super().__init__(cfg, name=name, priority=priority, random_seed=cfg.random_seed)
        self.config = self.cfg
        self._basis: Optional[np.ndarray] = None
        self._steps = 0

    def _reset_internal_state(self, solver: Any) -> None:
        _ = solver
        self._basis = None
        self._steps = 0
    def _before_propose(self, solver: Any, context: Dict[str, Any]) -> None:
        if self._basis is None or (self._steps % max(1, int(self.cfg.resample_every)) == 0):
            self._basis = self._build_or_sample_basis(solver)
        self._steps += 1

    def _sample_delta(self, solver: Any, context: Dict[str, Any]) -> np.ndarray:
        _ = solver, context
        assert self._basis is not None
        z = self._rng.uniform(low=-1.0, high=1.0, size=(self._basis.shape[1],))
        return self._basis @ z

    def _sample_subspace(self, solver: Any) -> np.ndarray:
        dim = int(getattr(solver, "dimension", 1) or 1)
        k = min(max(1, int(self.cfg.subspace_dim)), dim)
        mat = self._rng.normal(size=(dim, k))
        q, _ = np.linalg.qr(mat)
        return q[:, :k]

    def _build_or_sample_basis(self, solver: Any) -> np.ndarray:
        method = str(getattr(self.cfg, "basis_method", "random") or "random").strip().lower()
        if method == "random":
            return self._sample_subspace(solver)

        pop = getattr(solver, "population", None)
        if pop is None:
            return self._sample_subspace(solver)
        X = np.asarray(pop, dtype=float)
        if X.ndim != 2 or X.shape[0] < int(self.cfg.min_samples):
            return self._sample_subspace(solver)
        return self._build_basis_from_population(X, solver)

    def _build_basis_from_population(self, X: np.ndarray, solver: Any) -> np.ndarray:
        dim = int(getattr(solver, "dimension", X.shape[1]) or X.shape[1])
        k = min(max(1, int(self.cfg.subspace_dim)), dim)
        method = str(getattr(self.cfg, "basis_method", "random") or "random").strip().lower()
        if method == "random":
            return self._sample_subspace(solver)

        if method == "svd":
            Xc = X - np.mean(X, axis=0, keepdims=True)
            try:
                _, _, vt = np.linalg.svd(Xc, full_matrices=False)
                return vt[:k].T
            except Exception:
                return self._sample_subspace(solver)

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
                _ = labels
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
            return vt[:k].T
        except Exception:
            return self._sample_subspace(solver)

    def _score(
        self,
        solver: Any,
        objectives: np.ndarray,
        violations: np.ndarray,
        context: Dict[str, Any],
    ) -> np.ndarray:
        _ = solver, context
        obj = np.asarray(objectives, dtype=float)
        if obj.ndim == 1:
            obj = obj.reshape(-1, 1)
        vio = np.asarray(violations, dtype=float).reshape(-1)
        return np.sum(obj, axis=1) + vio * 1e6

    def _extra_state(self) -> Dict[str, Any]:
        return {
            "basis": None if self._basis is None else self._basis.tolist(),
            "steps": int(self._steps),
        }

    def _load_extra_state(self, state: Dict[str, Any]) -> None:
        basis = state.get("basis")
        self._basis = None if basis is None else np.asarray(basis, dtype=float)
        if state.get("steps") is not None:
            self._steps = int(state.get("steps"))
