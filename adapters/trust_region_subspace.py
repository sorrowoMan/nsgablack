"""
Subspace/low-rank trust-region (CUATRO_PLS-style) adapter.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

import numpy as np

from .trust_region_base import TrustRegionBaseAdapter
from ..utils.context.context_keys import KEY_SUBSPACE_BASIS


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
    context_notes = (
        "Optional key subspace_basis can inject a custom basis from context.",
    )

    def __init__(
        self,
        config: Optional[TrustRegionSubspaceConfig] = None,
        name: str = "trust_region_subspace",
        priority: int = 0,
    ) -> None:
        cfg = config or TrustRegionSubspaceConfig()
        super().__init__(cfg, name=name, priority=priority, random_seed=cfg.random_seed)
        self._basis: Optional[np.ndarray] = None
        self._steps = 0

    def _reset_internal_state(self, solver: Any) -> None:
        _ = solver
        self._basis = None
        self._steps = 0
    def _before_propose(self, solver: Any, context: Dict[str, Any]) -> None:
        basis_from_ctx = context.get(KEY_SUBSPACE_BASIS)
        if basis_from_ctx is not None:
            self._basis = np.asarray(basis_from_ctx, dtype=float)
        if self._basis is None or (self._steps % max(1, int(self.cfg.resample_every)) == 0):
            self._basis = self._sample_subspace(solver)
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
