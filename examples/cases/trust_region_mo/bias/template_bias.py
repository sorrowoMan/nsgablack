# -*- coding: utf-8 -*-
# Bias template: copy and customize for new bias components.

from __future__ import annotations

import numpy as np

from nsgablack.bias.core.base import BiasBase, OptimizationContext


class BiasTemplate(BiasBase):
    # Minimal runnable bias template.

    context_requires = ()
    context_provides = ()
    context_mutates = ()
    context_cache = ()
    context_notes = ("Bias template: compute a scalar bias from x/context.",)
    requires_metrics = ()
    metrics_fallback = "none"
    missing_metrics_policy = "warn"

    def __init__(self, weight: float = 1.0) -> None:
        super().__init__(name="bias_template", weight=float(weight), description="bias template")

    def compute(self, x: np.ndarray, context: OptimizationContext) -> float:
        _ = (x, context)
        return 0.0
