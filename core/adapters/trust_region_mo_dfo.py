"""
Multi-objective trust-region DFO adapter.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional, Sequence, Tuple, List

import numpy as np

from .algorithm_adapter import AlgorithmAdapter


@dataclass
class TrustRegionMODFOConfig:
    batch_size: int = 16
    initial_radius: float = 0.5
    min_radius: float = 1e-6
    max_radius: float = 2.0
    radius_expand: float = 1.5
    radius_shrink: float = 0.7
    success_tolerance: float = 1e-8
    include_center: bool = True
    weight_method: str = "dirichlet"  # "dirichlet" | "uniform" | "fixed"
    fixed_weights: Optional[Sequence[float]] = None
    random_seed: Optional[int] = None


class TrustRegionMODFOAdapter(AlgorithmAdapter):
    """
    Multi-objective trust-region derivative-free local search.

    Uses a scalarization weight vector to score candidates. Each update can
    resample weights to encourage coverage of different trade-offs.
    """

    def __init__(
        self,
        config: Optional[TrustRegionMODFOConfig] = None,
        name: str = "trust_region_mo_dfo",
        priority: int = 0,
    ) -> None:
        super().__init__(name=name, priority=priority)
        self.cfg = config or TrustRegionMODFOConfig()
        self._rng = np.random.default_rng(self.cfg.random_seed)
        self._center: Optional[np.ndarray] = None
        self._radius: float = float(self.cfg.initial_radius)
        self._best_score: Optional[float] = None
        self._weights: Optional[np.ndarray] = None

    def setup(self, solver: Any) -> None:
        self._radius = float(self.cfg.initial_radius)
        self._center = None
        self._best_score = None
        self._weights = None
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
        weights = self._get_weights(solver, context, objectives)
        scores = self._score(objectives, violations, weights)
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

    def get_state(self) -> Dict[str, Any]:
        return {
            "center": None if self._center is None else self._center.tolist(),
            "radius": float(self._radius),
            "best_score": None if self._best_score is None else float(self._best_score),
            "weights": None if self._weights is None else self._weights.tolist(),
        }

    def set_state(self, state: Dict[str, Any]) -> None:
        center = state.get("center")
        self._center = None if center is None else np.asarray(center, dtype=float)
        if state.get("radius") is not None:
            self._radius = float(state["radius"])
        self._best_score = state.get("best_score")
        weights = state.get("weights")
        self._weights = None if weights is None else np.asarray(weights, dtype=float)

    # ------------------------------------------------------------------
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

    def _get_weights(self, solver: Any, context: Dict[str, Any], objectives: np.ndarray) -> np.ndarray:
        if context and isinstance(context, dict) and "mo_weights" in context:
            try:
                w = np.asarray(context["mo_weights"], dtype=float).ravel()
                if w.size > 0:
                    self._weights = w / max(1e-12, float(np.sum(w)))
                    return self._weights
            except Exception:
                pass

        if self._weights is not None and self.cfg.weight_method == "fixed":
            return self._weights

        n_obj = int(getattr(solver, "num_objectives", 1) or 1)
        method = str(self.cfg.weight_method).lower().strip()
        if method == "fixed" and self.cfg.fixed_weights:
            w = np.asarray(self.cfg.fixed_weights, dtype=float).ravel()
            if w.size != n_obj:
                w = np.pad(w, (0, max(0, n_obj - w.size)))[:n_obj]
            w = w / max(1e-12, float(np.sum(w)))
            self._weights = w
            return w
        if method == "uniform":
            w = np.ones((n_obj,), dtype=float) / float(n_obj)
            self._weights = w
            return w

        # default: dirichlet random weights
        alpha = np.ones((n_obj,), dtype=float)
        w = self._rng.dirichlet(alpha)
        self._weights = w
        return w

    def _score(self, objectives: np.ndarray, violations: np.ndarray, weights: np.ndarray) -> np.ndarray:
        obj = np.asarray(objectives, dtype=float)
        if obj.ndim == 1:
            obj = obj.reshape(-1, 1)
        w = np.asarray(weights, dtype=float).ravel()
        if w.size != obj.shape[1]:
            w = np.ones((obj.shape[1],), dtype=float) / float(obj.shape[1])
        vio = np.asarray(violations, dtype=float).reshape(-1)
        return np.dot(obj, w) + vio * 1e6
