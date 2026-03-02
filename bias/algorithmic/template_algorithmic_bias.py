"""Template for an algorithmic bias."""
from __future__ import annotations

import numpy as np

from ..core.base import AlgorithmicBias, OptimizationContext


class ExampleAlgorithmicBias(AlgorithmicBias):
    """Template algorithmic bias that rewards diversity."""
    context_requires = ("population_ref",)
    context_provides = ()
    context_mutates = ()
    context_cache = ()
    context_notes = "Reads context fields: population_ref; outputs scalar bias only."



    def __init__(
        self,
        name: str = "example_algorithmic_bias",
        weight: float = 0.1,
        adaptive: bool = False,
    ):
        super().__init__(
            name=name,
            weight=weight,
            adaptive=adaptive,
            description="Template algorithmic bias (diversity reward).",
        )

    def compute(self, x: np.ndarray, context: OptimizationContext) -> float:
        pop = np.asarray(context.population) if context.population else None
        if pop is None or pop.size == 0:
            return 0.0
        center = np.mean(pop, axis=0)
        # Negative value = reward when added to objective (minimization).
        return -float(np.linalg.norm(x - center))
