"""
Non-smooth trust-region adapter (inexact model).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional, Sequence, Tuple, List

import numpy as np

from .algorithm_adapter import AlgorithmAdapter


@dataclass
class TrustRegionNonSmoothConfig:
    batch_size: int = 16
    initial_radius: float = 0.5
    min_radius: float = 1e-6
    max_radius: float = 2.0
    radius_expand: float = 1.3
    radius_shrink: float = 0.7
    success_tolerance: float = 1e-6
    include_center: bool = True
    score_mode: str = "l1"  # "l1" or "linf"
    random_seed: Optional[int] = None


class TrustRegionNonSmoothAdapter(AlgorithmAdapter):
    """
    Trust-region variant for non-smooth objectives.

    Uses L1/Linf aggregation to reduce sensitivity to kinks.
    """

    def __init__(
        self,
        config: Optional[TrustRegionNonSmoothConfig] = None,
        name: str = "trust_region_nonsmooth",
        priority: int = 0,
    ) -> None:
        super().__init__(name=name, priority=priority)
        self.cfg = config or TrustRegionNonSmoothConfig()
        self._rng = np.random.default_rng(self.cfg.random_seed)
        self._center: Optional[np.ndarray] = None
        self._radius: float = float(self.cfg.initial_radius)
        self._best_score: Optional[float] = None

    def setup(self, solver: Any) -> None:
        self._radius = float(self.cfg.initial_radius)
        self._center = None
        self._best_score = None
        return None

    def propose(self, solver: Any, context: Dict[str, Any]) -> Sequence[np.ndarray]:
        if self._center is None:
            self._center = self._init_center(solver)
        center = np.asarray(self._center, dtype=float)
        n = max(1, int(self.cfg.batch_size))
        candidates: List[np.ndarray] = []
        if bool(self.cfg.include_center):
            candidates.append(center.copy())
        while len(candidates) < n:
            delta = self._rng.uniform(low=-1.0, high=1.0, size=center.shape) * float(self._radius)
            cand = center + delta
            cand = self._clip_to_bounds(cand, solver)
            candidates.append(cand)
        return candidates

    def update(
        self,
        solver: Any,
        candidates: Sequence[np.ndarray],
        objectives: np.ndarray,
        violations: np.ndarray,
        context: Dict[str, Any],
    ) -> None:
        if candidates is None or len(candidates) == 0:
            return None
        scores = self._score(objectives, violations)
        best_idx = int(np.argmin(scores))
        best_score = float(scores[best_idx])
        improved = (
            self._best_score is None
            or (self._best_score - best_score) > float(self.cfg.success_tolerance)
        )
        if improved:
            self._best_score = best_score
            self._center = np.asarray(candidates[best_idx], dtype=float).copy()
            self._radius = min(float(self._radius) * float(self.cfg.radius_expand), float(self.cfg.max_radius))
        else:
            self._radius = max(float(self._radius) * float(self.cfg.radius_shrink), float(self.cfg.min_radius))
        return None

    def _score(self, objectives: np.ndarray, violations: np.ndarray) -> np.ndarray:
        obj = np.asarray(objectives, dtype=float)
        if obj.ndim == 1:
            obj = obj.reshape(-1, 1)
        mode = str(self.cfg.score_mode).lower().strip()
        if mode == "linf":
            agg = np.max(np.abs(obj), axis=1)
        else:
            agg = np.sum(np.abs(obj), axis=1)
        vio = np.asarray(violations, dtype=float).reshape(-1)
        return agg + vio * 1e6

    def _init_center(self, solver: Any) -> np.ndarray:
        if getattr(solver, "best_x", None) is not None:
            return np.asarray(solver.best_x, dtype=float)
        pipeline = getattr(solver, "representation_pipeline", None)
        if pipeline is not None and hasattr(pipeline, "init"):
            try:
                return np.asarray(pipeline.init(solver.problem, context=None), dtype=float)
            except Exception:
                pass
        low, high = self._extract_bounds(solver)
        if low is None or high is None:
            dim = int(getattr(solver, "dimension", 1) or 1)
            return self._rng.uniform(low=-1.0, high=1.0, size=(dim,))
        return self._rng.uniform(low=low, high=high)

    def _extract_bounds(self, solver: Any) -> Tuple[Optional[np.ndarray], Optional[np.ndarray]]:
        bounds = getattr(getattr(solver, "problem", None), "bounds", None)
        if bounds is None:
            return None, None
        if isinstance(bounds, dict):
            vals = list(bounds.values())
        else:
            vals = list(bounds)
        low = np.asarray([float(v[0]) for v in vals], dtype=float)
        high = np.asarray([float(v[1]) for v in vals], dtype=float)
        return low, high

    def _clip_to_bounds(self, x: np.ndarray, solver: Any) -> np.ndarray:
        low, high = self._extract_bounds(solver)
        if low is None or high is None:
            return x
        return np.minimum(np.maximum(x, low), high)
