"""
Model-and-Search (MAS) adapter: alternates model update and search steps.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional, Sequence, List

import numpy as np

from ..algorithm_adapter import AlgorithmAdapter
from ...utils.context.context_keys import KEY_BEST_X
from ...utils.surrogate.vector_surrogate import VectorSurrogate


@dataclass
class MASConfig:
    batch_size: int = 16
    exploration_ratio: float = 0.4
    random_seed: Optional[int] = None
    enable_surrogate: bool = True
    surrogate_model_type: str = "rf"
    surrogate_min_train_samples: int = 20
    surrogate_max_train_samples: int = 5000
    surrogate_retrain_every_call: bool = True


class MASAdapter(AlgorithmAdapter):
    """
    MAS adapter (model-and-search).

    This adapter maintains an optional internal surrogate model for exploitation.
    """
    context_requires = ("generation",)
    context_provides = ()
    context_mutates = ()
    context_cache = ()
    context_notes = ("Optional model-assisted search using internal surrogate.",)
    state_recovery_level = "L1"
    state_recovery_notes = "Restores adaptive center; surrogate cache is rebuilt from adapter history."

    def __init__(
        self,
        config: Optional[MASConfig] = None,
        name: str = "mas",
        priority: int = 0,
        **config_kwargs,
    ) -> None:
        super().__init__(name=name, priority=priority)
        self.config = self.resolve_config(
            config=config,
            config_cls=MASConfig,
            config_kwargs=config_kwargs,
            adapter_name="MASAdapter",
        )
        self.cfg = self.config
        self._rng = np.random.default_rng(self.cfg.random_seed)
        self._center: Optional[np.ndarray] = None
        self._surrogate: Optional[VectorSurrogate] = None
        self._X: list[np.ndarray] = []
        self._Y: list[np.ndarray] = []

    def propose(self, solver: Any, context: Dict[str, Any]) -> Sequence[np.ndarray]:
        if self._center is None:
            self._center = self._init_center(solver, context)
        center = np.asarray(self._center, dtype=float)
        n = max(1, int(self.cfg.batch_size))
        explore_n = int(round(n * float(self.cfg.exploration_ratio)))
        exploit_n = max(0, n - explore_n)

        candidates: List[np.ndarray] = []
        # exploration: random neighborhood
        for _ in range(explore_n):
            cand = center + self._rng.normal(size=center.shape) * 0.5
            candidates.append(self._clip_to_bounds(cand, solver))

        # exploitation: use surrogate model if available
        model = self._surrogate
        if model is not None and exploit_n > 0:
            pool = [center + self._rng.normal(size=center.shape) * 0.5 for _ in range(exploit_n * 3)]
            pool_arr = np.stack(pool, axis=0)
            try:
                preds = np.asarray(model.predict(pool_arr), dtype=float)
                if preds.ndim == 1:
                    scores = preds.reshape(-1)
                else:
                    scores = np.sum(preds, axis=1)
            except Exception:
                scores = np.asarray([np.sum(p ** 2) for p in pool_arr], dtype=float)
            best_idx = np.argsort(scores)[:exploit_n]
            for idx in best_idx:
                candidates.append(self._clip_to_bounds(pool_arr[idx], solver))
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
        self._center = np.asarray(candidates[best_idx], dtype=float).copy()
        self._update_surrogate(candidates, objectives)
        return None

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

    def _extract_bounds(self, solver: Any) -> tuple[Optional[np.ndarray], Optional[np.ndarray]]:
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

    def get_state(self) -> Dict[str, Any]:
        return {
            "center": None if self._center is None else self._center.tolist(),
        }

    def set_state(self, state: Dict[str, Any]) -> None:
        if not state:
            return
        center = state.get("center")
        self._center = None if center is None else np.asarray(center, dtype=float)

    def _score(self, objectives: np.ndarray, violations: np.ndarray) -> np.ndarray:
        obj = np.asarray(objectives, dtype=float)
        if obj.ndim == 1:
            obj = obj.reshape(-1, 1)
        vio = np.asarray(violations, dtype=float).reshape(-1)
        return np.sum(obj, axis=1) + vio * 1e6

    def _ensure_surrogate(self, solver: Any, objectives: Optional[np.ndarray] = None) -> None:
        if not bool(self.cfg.enable_surrogate):
            return None
        if self._surrogate is not None:
            return None
        n_obj = None
        if objectives is not None:
            obj = np.asarray(objectives, dtype=float)
            if obj.ndim == 1:
                n_obj = 1
            elif obj.ndim >= 2:
                n_obj = int(obj.shape[1])
        if n_obj is None:
            n_obj = int(getattr(solver, "num_objectives", 1) or 1)
        self._surrogate = VectorSurrogate(num_objectives=int(n_obj), model_type=self.cfg.surrogate_model_type)

    def _update_surrogate(self, candidates: Sequence[np.ndarray], objectives: np.ndarray) -> None:
        if not bool(self.cfg.enable_surrogate):
            return None
        if candidates is None or len(candidates) == 0:
            return None
        obj = np.asarray(objectives, dtype=float)
        if obj.ndim == 1:
            obj = obj.reshape(-1, 1)
        self._ensure_surrogate(self.solver, obj if obj.size else None)
        if self._surrogate is None:
            return None
        X = [np.asarray(c, dtype=float).reshape(-1) for c in candidates]
        Y = [np.asarray(row, dtype=float).reshape(-1) for row in obj]
        self._X.extend(X)
        self._Y.extend(Y)

        max_keep = max(0, int(self.cfg.surrogate_max_train_samples))
        if max_keep > 0 and len(self._X) > max_keep:
            overflow = len(self._X) - max_keep
            del self._X[:overflow]
            del self._Y[:overflow]

        if len(self._X) >= int(self.cfg.surrogate_min_train_samples) and bool(
            self.cfg.surrogate_retrain_every_call
        ):
            X_arr = np.asarray(self._X, dtype=float)
            Y_arr = np.asarray(self._Y, dtype=float)
            try:
                self._surrogate.fit(X_arr, Y_arr)
            except Exception:
                return None
        return None
