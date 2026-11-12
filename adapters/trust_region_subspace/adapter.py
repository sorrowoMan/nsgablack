"""
Subspace/low-rank trust-region (CUATRO_PLS-style) adapter.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

import numpy as np

from ..trust_region_base import TrustRegionBaseAdapter
from ...core.state.solution_pool import SolutionRef


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
    sample_limit: int = 256
    resample_every: int = 10
    random_seed: Optional[int] = None


class TrustRegionSubspaceAdapter(TrustRegionBaseAdapter):
    """
    Trust-region local search in a low-dimensional subspace.

    Uses a random orthonormal subspace and samples within it.
    """
    unit_build_operations = ("initialize", "basis")
    context_requires = ("generation",)
    context_provides = ()
    context_mutates = ()
    context_cache = ()
    context_notes = ("Adapter schedules basis refresh from its own accepted task samples; the algorithm pipeline constructs the basis.",)

    def __init__(
        self,
        config: Optional[TrustRegionSubspaceConfig] = None,
        name: str = "trust_region_subspace",
        priority: int = 0,
        *,
        initializer=None,
        repair=None,
        **config_kwargs,
    ) -> None:
        unit_binding = config_kwargs.pop("unit_binding", None)
        cfg = self.resolve_config(
            config=config,
            config_cls=TrustRegionSubspaceConfig,
            config_kwargs=config_kwargs,
            adapter_name="TrustRegionSubspaceAdapter",
        )
        super().__init__(cfg, name=name, priority=priority, random_seed=cfg.random_seed,
                         unit_binding=unit_binding, initializer=initializer, repair=repair)
        self.config = self.cfg
        if int(cfg.sample_limit) < max(1, int(cfg.min_samples)):
            raise ValueError("subspace sample_limit must cover min_samples")
        self._basis: Optional[np.ndarray] = None
        self._steps = 0
        self._sample_refs = ()

    def _reset_internal_state(self, control: Any) -> None:
        _ = control
        self._basis = None
        self._steps = 0
        self._sample_refs = ()

    def _record_reference_samples(self, control, candidates, feedback, scores, violations):
        refs = list(self._sample_refs)
        for index in range(len(candidates)):
            selected = self._pool_results.capture(control, candidates, feedback, index, scores[index], violations[index])
            if selected.ref is None:
                raise ValueError("subspace samples require exact accepted solution references")
            if selected.ref not in refs:
                refs.append(selected.ref)
        self._sample_refs = tuple(refs[-int(self.cfg.sample_limit):])

    def get_solution_pool_roots(self, control):
        return tuple(dict.fromkeys((*super().get_solution_pool_roots(control), *self._sample_refs)))
    def _before_propose(self, control: Any, context: Dict[str, Any]) -> None:
        if self._basis is None or (self._steps % max(1, int(self.cfg.resample_every)) == 0):
            self._basis = self._build_or_sample_basis(control)
        self._steps += 1

    def _repair_within_region(self, candidate: np.ndarray) -> bool:
        if self._basis is None:
            return False
        delta = np.asarray(candidate, dtype=float) - np.asarray(self._center, dtype=float)
        coordinates = self._basis.T @ delta
        tolerance = 1e-12 * max(1.0, abs(self._radius))
        return bool(np.all(np.isfinite(delta))
                    and np.max(np.abs(delta - self._basis @ coordinates), initial=0.0) <= tolerance
                    and np.max(np.abs(coordinates), initial=0.0) <= self._radius + tolerance)

    def _sample_delta(self, control: Any, context: Dict[str, Any]) -> np.ndarray:
        _ = control, context
        assert self._basis is not None
        z = self._rng.uniform(low=-1.0, high=1.0, size=(self._basis.shape[1],))
        return self._basis @ z

    def _clip_to_bounds(self, x: np.ndarray, control: Any) -> np.ndarray:
        # Coordinate clipping generally leaves a low-dimensional subspace.
        # Shorten the same ray so its basis coordinates remain admissible.
        low, high = self._extract_bounds(control)
        if low is None or high is None:
            return x
        delta = np.asarray(x, dtype=float) - self._center
        scale = 1.0
        positive, negative = delta > 0, delta < 0
        if np.any(positive):
            scale = min(scale, float(np.min((high[positive] - self._center[positive]) / delta[positive])))
        if np.any(negative):
            scale = min(scale, float(np.min((low[negative] - self._center[negative]) / delta[negative])))
        return self._center + max(0., scale) * delta

    def _sample_subspace(self, control: Any) -> np.ndarray:
        dim = int(getattr(control, "dimension", 1) or 1)
        k = min(max(1, int(self.cfg.subspace_dim)), dim)
        self.rebuild_unit("basis", method="random", rank=k,
                          samples=self._rng.normal(size=(dim, k)))
        return self.ensure_unit().basis

    def _build_or_sample_basis(self, control: Any) -> np.ndarray:
        method = str(getattr(self.cfg, "basis_method", "random") or "random").strip().lower()
        if method == "random":
            return self._sample_subspace(control)

        if len(self._sample_refs) < int(self.cfg.min_samples):
            return self._sample_subspace(control)
        X = control.solution_pool.read(self._sample_refs, allow_pending=True).numeric_matrix
        return self._build_basis_from_population(X, control)

    def _build_basis_from_population(self, X: np.ndarray, control: Any) -> np.ndarray:
        dim = int(getattr(control, "dimension", X.shape[1]) or X.shape[1])
        k = min(max(1, int(self.cfg.subspace_dim)), dim)
        method = str(getattr(self.cfg, "basis_method", "random") or "random").strip().lower()
        if method == "random":
            return self._sample_subspace(control)

        try:
            self.rebuild_unit("basis", method=method, rank=k, samples=X, seed=self.cfg.random_seed)
            return self.ensure_unit().basis
        except (ImportError, ValueError, np.linalg.LinAlgError):
            if method in {"sparse_pca", "cluster"}:
                try:
                    self.rebuild_unit("basis", method="pca", rank=k, samples=X)
                    return self.ensure_unit().basis
                except np.linalg.LinAlgError:
                    pass
            return self._sample_subspace(control)

    def _score(
        self,
        control: Any,
        objectives: np.ndarray,
        violations: np.ndarray,
        context: Dict[str, Any],
    ) -> np.ndarray:
        _ = control, context
        obj = np.asarray(objectives, dtype=float)
        if obj.ndim == 1:
            obj = obj.reshape(-1, 1)
        vio = np.asarray(violations, dtype=float).reshape(-1)
        return np.sum(obj, axis=1) + vio * 1e6

    def _extra_state(self) -> Dict[str, Any]:
        return {
            "basis": None if self._basis is None else self._basis.tolist(),
            "steps": int(self._steps),
            "sample_refs": [ref.as_dict() for ref in self._sample_refs],
        }

    def _load_extra_state(self, state: Dict[str, Any]) -> None:
        basis = state.get("basis")
        self._basis = None if basis is None else np.asarray(basis, dtype=float)
        self._sample_refs = tuple(SolutionRef.from_dict(value) for value in state.get("sample_refs", ()))
        if len(set(self._sample_refs)) != len(self._sample_refs) or len(self._sample_refs) > int(self.cfg.sample_limit):
            raise ValueError("invalid restored subspace sample reference window")
        if state.get("steps") is not None:
            self._steps = int(state.get("steps"))
