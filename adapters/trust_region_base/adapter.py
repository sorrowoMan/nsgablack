"""
Shared base for trust-region adapters.
"""

from __future__ import annotations

from abc import abstractmethod
from typing import Any, Dict, Optional, Sequence, Tuple, List

import numpy as np

from ..algorithm_adapter import AlgorithmAdapter
from ...utils.context.context_keys import KEY_BEST_X


class TrustRegionBaseAdapter(AlgorithmAdapter):
    """
    Common trust-region behavior:
    - center initialization
    - trust-radius expand/shrink
    - candidate propose loop
    - state roundtrip
    """
    context_requires = ()
    context_provides = ()
    context_mutates = ()
    context_cache = ()
    context_notes = "Shared trust-region base class; concrete adapters define sampling and scoring."
    state_recovery_level = "L1"
    state_recovery_notes = "Restores center/radius/best score and subclass extra state."

    def __init__(
        self,
        config: Any,
        *,
        name: str,
        priority: int = 0,
        random_seed: Optional[int] = None,
    ) -> None:
        super().__init__(name=name, priority=priority)
        self.cfg = config
        self._rng = np.random.default_rng(random_seed)
        self._center: Optional[np.ndarray] = None
        self._radius: float = float(getattr(self.cfg, "initial_radius", 0.5))
        self._best_score: Optional[float] = None

    def setup(self, solver: Any) -> None:
        self._radius = float(getattr(self.cfg, "initial_radius", 0.5))
        self._center = None
        self._best_score = None
        self._reset_internal_state(solver)

    def propose(self, solver: Any, context: Dict[str, Any]) -> Sequence[np.ndarray]:
        if self._center is None:
            self._center = self._init_center(solver, context)

        self._before_propose(solver, context)
        center = np.asarray(self._center, dtype=float)
        n = max(1, int(getattr(self.cfg, "batch_size", 1)))
        candidates: List[np.ndarray] = []
        if bool(getattr(self.cfg, "include_center", True)):
            candidates.append(center.copy())
        while len(candidates) < n:
            delta = np.asarray(self._sample_delta(solver, context), dtype=float)
            cand = center + (delta * float(self._radius))
            cand = self._clip_to_bounds(cand, solver)
            candidates.append(cand)
        self._after_propose(solver, context)
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
            return
        scores = np.asarray(self._score(solver, objectives, violations, context), dtype=float).reshape(-1)
        if scores.size == 0:
            return
        best_idx = int(np.argmin(scores))
        best_score = float(scores[best_idx])
        improved = (
            self._best_score is None
            or (float(self._best_score) - best_score) > float(getattr(self.cfg, "success_tolerance", 1e-8))
        )
        if improved:
            self._best_score = best_score
            self._center = np.asarray(candidates[best_idx], dtype=float).copy()
            self._radius = min(
                float(self._radius) * float(getattr(self.cfg, "radius_expand", 1.5)),
                float(getattr(self.cfg, "max_radius", 2.0)),
            )
        else:
            self._radius = max(
                float(self._radius) * float(getattr(self.cfg, "radius_shrink", 0.7)),
                float(getattr(self.cfg, "min_radius", 1e-6)),
            )
        self._after_update(solver, candidates, objectives, violations, context, improved=improved)

    def get_state(self) -> Dict[str, Any]:
        state: Dict[str, Any] = {
            "center": None if self._center is None else self._center.tolist(),
            "radius": float(self._radius),
            "best_score": None if self._best_score is None else float(self._best_score),
        }
        extra = self._extra_state()
        if extra:
            state.update(extra)
        return state

    def set_state(self, state: Dict[str, Any]) -> None:
        if not state:
            return
        center = state.get("center")
        self._center = None if center is None else np.asarray(center, dtype=float)
        if state.get("radius") is not None:
            self._radius = float(state["radius"])
        self._best_score = state.get("best_score")
        self._load_extra_state(state)

    def _init_center(self, solver: Any, context: Optional[Dict[str, Any]] = None) -> np.ndarray:
        if isinstance(context, dict):
            best_ctx = context.get(KEY_BEST_X)
            if best_ctx is not None:
                return np.asarray(best_ctx, dtype=float)
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

    # Hooks
    def _reset_internal_state(self, solver: Any) -> None:
        _ = solver

    def _before_propose(self, solver: Any, context: Dict[str, Any]) -> None:
        _ = solver, context

    def _after_propose(self, solver: Any, context: Dict[str, Any]) -> None:
        _ = solver, context

    def _after_update(
        self,
        solver: Any,
        candidates: Sequence[np.ndarray],
        objectives: np.ndarray,
        violations: np.ndarray,
        context: Dict[str, Any],
        *,
        improved: bool,
    ) -> None:
        _ = solver, candidates, objectives, violations, context, improved

    def _extra_state(self) -> Dict[str, Any]:
        return {}

    def _load_extra_state(self, state: Dict[str, Any]) -> None:
        _ = state

    # Required in subclasses
    @abstractmethod
    def _sample_delta(self, solver: Any, context: Dict[str, Any]) -> np.ndarray:
        raise NotImplementedError

    @abstractmethod
    def _score(
        self,
        solver: Any,
        objectives: np.ndarray,
        violations: np.ndarray,
        context: Dict[str, Any],
    ) -> np.ndarray:
        raise NotImplementedError
