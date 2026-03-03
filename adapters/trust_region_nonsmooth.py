"""
Non-smooth trust-region adapter (inexact model).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

import numpy as np

from .trust_region_base import TrustRegionBaseAdapter


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


class TrustRegionNonSmoothAdapter(TrustRegionBaseAdapter):
    """
    Trust-region variant for non-smooth objectives.

    Uses L1/Linf aggregation to reduce sensitivity to kinks.
    """
    context_requires = ("generation",)
    context_provides = ()
    context_mutates = ()
    context_cache = ()
    context_notes = "Non-smooth trust-region search with L1/Linf objective aggregation."

    def __init__(
        self,
        config: Optional[TrustRegionNonSmoothConfig] = None,
        name: str = "trust_region_nonsmooth",
        priority: int = 0,
    ) -> None:
        cfg = config or TrustRegionNonSmoothConfig()
        super().__init__(cfg, name=name, priority=priority, random_seed=cfg.random_seed)

    def _sample_delta(self, solver: Any, context: Dict[str, Any]) -> np.ndarray:
        _ = solver, context
        assert self._center is not None
        return self._rng.uniform(low=-1.0, high=1.0, size=self._center.shape)

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
        mode = str(self.cfg.score_mode).lower().strip()
        if mode == "linf":
            agg = np.max(np.abs(obj), axis=1)
        else:
            agg = np.sum(np.abs(obj), axis=1)
        vio = np.asarray(violations, dtype=float).reshape(-1)
        return agg + vio * 1e6
