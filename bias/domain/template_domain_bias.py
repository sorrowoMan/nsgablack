"""Template for a domain (business) bias."""
from __future__ import annotations

import numpy as np

from ..core.base import DomainBias, OptimizationContext


class ExampleDomainBias(DomainBias):
    """Template domain bias that enforces a soft business rule."""

    def __init__(
        self,
        name: str = "example_domain_bias",
        weight: float = 1.0,
        limit: float = 1000.0,
    ):
        super().__init__(
            name=name,
            weight=weight,
            mandatory=True,
            description="Template domain bias (soft sum limit).",
        )
        self.limit = float(limit)

    def compute(self, x: np.ndarray, context: OptimizationContext) -> float:
        # Penalize if the sum exceeds the limit.
        return max(0.0, float(np.sum(x)) - self.limit)
