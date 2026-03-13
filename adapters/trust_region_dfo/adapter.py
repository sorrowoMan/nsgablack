"""
Derivative-free trust-region local search adapter.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

import numpy as np

from ..trust_region_base import TrustRegionBaseAdapter


@dataclass
class TrustRegionDFOConfig:
    batch_size: int = 16
    initial_radius: float = 0.5
    min_radius: float = 1e-6
    max_radius: float = 2.0
    radius_expand: float = 1.5
    radius_shrink: float = 0.7
    success_tolerance: float = 1e-8
    include_center: bool = True
    random_seed: Optional[int] = None


class TrustRegionDFOAdapter(TrustRegionBaseAdapter):
    """
    Trust-region derivative-free local search.

    Uses a center point and samples candidates within a trust radius.
    Radius expands on improvement and shrinks on stagnation.
    """
    context_requires = ("generation",)
    context_provides = ()
    context_mutates = ()
    context_cache = ()
    context_notes = "Trust-region local search; context is only used as runtime metadata."

    def __init__(
        self,
        config: Optional[TrustRegionDFOConfig] = None,
        name: str = "trust_region_dfo",
        priority: int = 0,
        **config_kwargs,
    ) -> None:
        cfg = self.resolve_config(
            config=config,
            config_cls=TrustRegionDFOConfig,
            config_kwargs=config_kwargs,
            adapter_name="TrustRegionDFOAdapter",
        )
        super().__init__(cfg, name=name, priority=priority, random_seed=cfg.random_seed)
        self.config = self.cfg

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
        vio = np.asarray(violations, dtype=float).reshape(-1)
        return np.sum(obj, axis=1) + vio * 1e6
