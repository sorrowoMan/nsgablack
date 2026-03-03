"""
Multi-objective trust-region DFO adapter.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional, Sequence

import numpy as np

from .trust_region_base import TrustRegionBaseAdapter
from ..utils.context.context_keys import KEY_MO_WEIGHTS


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

    Uses a scalarization weight vector to score candidates. Each update can
    resample weights to encourage coverage of different trade-offs.
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
    ) -> None:
        cfg = config or TrustRegionMODFOConfig()
        super().__init__(cfg, name=name, priority=priority, random_seed=cfg.random_seed)
        self._weights: Optional[np.ndarray] = None

    def _reset_internal_state(self, solver: Any) -> None:
        _ = solver
        self._weights = None
    def _sample_delta(self, solver: Any, context: Dict[str, Any]) -> np.ndarray:
        _ = solver, context
        assert self._center is not None
        return self._rng.uniform(low=-1.0, high=1.0, size=self._center.shape)

    def _get_weights(self, solver: Any, context: Dict[str, Any], objectives: np.ndarray) -> np.ndarray:
        if context and isinstance(context, dict) and KEY_MO_WEIGHTS in context:
            try:
                w = np.asarray(context[KEY_MO_WEIGHTS], dtype=float).ravel()
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

    def _score(
        self,
        solver: Any,
        objectives: np.ndarray,
        violations: np.ndarray,
        context: Dict[str, Any],
    ) -> np.ndarray:
        weights = self._get_weights(solver, context, objectives)
        obj = np.asarray(objectives, dtype=float)
        if obj.ndim == 1:
            obj = obj.reshape(-1, 1)
        w = np.asarray(weights, dtype=float).ravel()
        if w.size != obj.shape[1]:
            w = np.ones((obj.shape[1],), dtype=float) / float(obj.shape[1])
        vio = np.asarray(violations, dtype=float).reshape(-1)
        return np.dot(obj, w) + vio * 1e6

    def _extra_state(self) -> Dict[str, Any]:
        return {"weights": None if self._weights is None else self._weights.tolist()}

    def _load_extra_state(self, state: Dict[str, Any]) -> None:
        weights = state.get("weights")
        self._weights = None if weights is None else np.asarray(weights, dtype=float)
