"""
Multi-objective trust-region DFO adapter.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any, Dict, Optional, Sequence

import numpy as np

from ..trust_region_base import TrustRegionBaseAdapter
from nsgablack.context_keys import KEY_MO_WEIGHTS


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


class TrustRegionMODFOAdapter(TrustRegionBaseAdapter):
    """
    Multi-objective trust-region derivative-free local search.

    Ordinary search resamples scalarization weights and rescores its retained
    selections in that same frame. A pool task freezes its native weights;
    projected tasks use the external projection instead of this scalarization.
    """
    context_requires = ("generation",)
    context_provides = ()
    context_mutates = ()
    context_cache = ()
    context_notes = (
        "Optional key mo_weights can provide external scalarization weights.",
    )

    def __init__(
        self,
        config: Optional[TrustRegionMODFOConfig] = None,
        name: str = "trust_region_mo_dfo",
        priority: int = 0,
        **config_kwargs,
    ) -> None:
        unit_binding = config_kwargs.pop("unit_binding", None)
        cfg = self.resolve_config(
            config=config,
            config_cls=TrustRegionMODFOConfig,
            config_kwargs=config_kwargs,
            adapter_name="TrustRegionMODFOAdapter",
        )
        super().__init__(cfg, name=name, priority=priority, random_seed=cfg.random_seed, unit_binding=unit_binding)
        self.config = self.cfg
        self._weights: Optional[np.ndarray] = None

    def _reset_internal_state(self, control: Any) -> None:
        _ = control
        self._weights = None
    def _sample_delta(self, control: Any, context: Dict[str, Any]) -> np.ndarray:
        _ = control, context
        assert self._center is not None
        return self._rng.uniform(low=-1.0, high=1.0, size=self._center.shape)

    def _get_weights(self, control: Any, context: Dict[str, Any], objectives: np.ndarray) -> np.ndarray:
        n_obj = np.asarray(objectives).shape[1] if np.asarray(objectives).ndim == 2 else 1
        supplied = None
        if context and isinstance(context, dict) and KEY_MO_WEIGHTS in context:
            supplied = self._normalize_weights(context[KEY_MO_WEIGHTS], n_obj)
        if self._weights is not None and self._pool_input_task:
            if supplied is not None and not np.array_equal(supplied, self._weights):
                raise ValueError("trust-region task weights changed without restart")
            if self._weights.size != n_obj:
                raise ValueError("trust-region task objective dimension changed")
            return self._weights
        if supplied is not None:
            self._weights = supplied
            return self._weights
        method = str(self.cfg.weight_method).lower().strip()
        if self._weights is not None and method == "fixed":
            return self._normalize_weights(self._weights, n_obj)
        if method == "fixed" and self.cfg.fixed_weights is not None:
            self._weights = self._normalize_weights(self.cfg.fixed_weights, n_obj)
            return self._weights
        if method == "uniform":
            w = np.ones((n_obj,), dtype=float) / float(n_obj)
            self._weights = w
            return w
        if method not in {"dirichlet", "fixed"}:
            raise ValueError(f"unknown trust-region weight method: {method}")
        alpha = np.ones((n_obj,), dtype=float)
        w = self._rng.dirichlet(alpha)
        self._weights = w
        return w

    @staticmethod
    def _normalize_weights(value, n_obj):
        weights = np.asarray(value, dtype=float).reshape(-1)
        if (weights.size != n_obj or not np.all(np.isfinite(weights))
                or np.any(weights < 0) or float(weights.sum()) <= 0):
            raise ValueError("trust-region weights must be finite, nonnegative and match objective dimension")
        return weights / float(weights.sum())

    def _rescore_selections(self, weights):
        # Historical scalar scores cannot be compared to a newly sampled
        # direction. Keep evaluated vectors, never reevaluate the Problem.
        for field in ("current", "best"):
            selected = getattr(self._pool_results, field)
            if selected is None:
                continue
            objectives = np.asarray(self._selection_objectives[field], dtype=float)
            if objectives.shape != weights.shape or not np.all(np.isfinite(objectives)):
                raise ValueError("trust-region selection lacks aligned objective evidence")
            score = float(objectives @ weights + selected.violation * 1e6)
            setattr(self._pool_results, field, replace(selected, score=score))
        current, best = self._pool_results.current, self._pool_results.best
        if current is not None:
            self._best_score = current.score
            if best is None or current.score < best.score:
                self._pool_results.best = current
                self._selection_objectives["best"] = list(self._selection_objectives["current"])

    def _score(
        self,
        control: Any,
        objectives: np.ndarray,
        violations: np.ndarray,
        context: Dict[str, Any],
    ) -> np.ndarray:
        weights = self._get_weights(control, context, objectives)
        obj = np.asarray(objectives, dtype=float)
        if obj.ndim == 1:
            obj = obj.reshape(-1, 1)
        w = np.asarray(weights, dtype=float).ravel()
        self._rescore_selections(w)
        vio = np.asarray(violations, dtype=float).reshape(-1)
        return np.dot(obj, w) + vio * 1e6

    def _extra_state(self) -> Dict[str, Any]:
        return {"weights": None if self._weights is None else self._weights.tolist()}

    def _load_extra_state(self, state: Dict[str, Any]) -> None:
        weights = state.get("weights")
        self._weights = None if weights is None else np.asarray(weights, dtype=float)
