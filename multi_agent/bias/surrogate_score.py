"""Surrogate-based score bias for advisor candidates."""
from __future__ import annotations

from typing import Optional, Sequence
import numpy as np

try:
    from ...surrogate import SurrogateManager
except Exception:
    try:
        from surrogate import SurrogateManager
    except Exception:  # pragma: no cover - optional dependency
        SurrogateManager = None


class SurrogateScoreBias:
    """Use a surrogate model to score advisor candidates."""

    def __init__(
        self,
        surrogate_manager: SurrogateManager,
        weight: float = 1.0,
        sign: float = -1.0,
        mode: str = 'mean',
        objective_weights: Optional[Sequence[float]] = None,
        use_uncertainty: bool = False,
        uncertainty_weight: float = 0.0,
        min_samples: int = 5,
        fallback_score: float = 0.0,
    ):
        self.surrogate_manager = surrogate_manager
        self.weight = float(weight)
        self.sign = float(sign)
        self.mode = str(mode).lower()
        self.objective_weights = objective_weights
        self.use_uncertainty = bool(use_uncertainty)
        self.uncertainty_weight = float(uncertainty_weight)
        self.min_samples = max(0, int(min_samples))
        self.fallback_score = float(fallback_score)

    def compute_score(self, x, constraints=None, context=None) -> float:
        if not self._ready():
            return self.fallback_score
        x_arr = np.asarray(x, dtype=float).reshape(1, -1)
        pred = self._predict(x_arr)
        if pred is None:
            return self.fallback_score
        score = self._to_scalar(pred)
        if self.use_uncertainty:
            score += self.uncertainty_weight * self._uncertainty(x_arr)
        return float(self.sign * self.weight * score)

    def score(self, x, constraints=None, context=None) -> float:
        return self.compute_score(x, constraints, context)

    def __call__(self, x, constraints=None, context=None) -> float:
        return self.compute_score(x, constraints, context)

    def _ready(self) -> bool:
        if self.surrogate_manager is None:
            return False
        model = getattr(self.surrogate_manager, 'surrogate_model', None)
        if model is None:
            return False
        if hasattr(model, 'X_train'):
            try:
                return len(model.X_train) >= self.min_samples
            except Exception:
                return bool(getattr(model, 'is_trained', False))
        return bool(getattr(model, 'is_trained', False))

    def _predict(self, x_arr: np.ndarray) -> Optional[np.ndarray]:
        try:
            pred = self.surrogate_manager.predict(x_arr)
            pred_arr = np.asarray(pred, dtype=float)
            if pred_arr.ndim == 0:
                pred_arr = pred_arr.reshape(1, 1)
            elif pred_arr.ndim == 1:
                pred_arr = pred_arr.reshape(1, -1)
            return pred_arr
        except Exception:
            return None

    def _uncertainty(self, x_arr: np.ndarray) -> float:
        if self.surrogate_manager is None:
            return 0.0
        try:
            unc = self.surrogate_manager.get_uncertainty(x_arr)
            unc_arr = np.asarray(unc, dtype=float)
            if unc_arr.ndim == 0:
                return float(unc_arr)
            if unc_arr.ndim == 1:
                return float(np.mean(unc_arr))
            return float(np.mean(unc_arr))
        except Exception:
            return 0.0

    def _to_scalar(self, pred: np.ndarray) -> float:
        pred_arr = np.asarray(pred, dtype=float)
        if pred_arr.ndim == 0:
            return float(pred_arr)
        if pred_arr.ndim == 1:
            return float(np.mean(pred_arr))
        if pred_arr.shape[1] == 1:
            return float(pred_arr[0, 0])
        if self.objective_weights is None:
            return float(np.mean(pred_arr[0]))
        weights = np.asarray(self.objective_weights, dtype=float).flatten()
        if weights.size != pred_arr.shape[1]:
            weights = np.ones(pred_arr.shape[1], dtype=float)
        w_sum = np.sum(weights)
        if w_sum <= 0:
            weights = np.ones(pred_arr.shape[1], dtype=float)
            w_sum = float(pred_arr.shape[1])
        weights = weights / w_sum
        return float(np.sum(pred_arr[0] * weights))
