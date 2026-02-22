# -*- coding: utf-8 -*-
"""Bias template / 偏置模板。"""

from __future__ import annotations

import numpy as np

from nsgablack.bias.core.base import BiasBase, OptimizationContext
from nsgablack.catalog.markers import component


@component(kind="bias")
class BiasTemplate(BiasBase):
    # TODO(中/EN): 仅声明真实读写字段 / declare only real read-write fields.
    context_requires = ()
    context_provides = ()
    context_mutates = ()
    context_cache = ()
    context_notes = ("TODO(中/EN): 一句话说明 context 契约 / one-line context contract.",)

    requires_metrics = ()
    metrics_fallback = "none"
    missing_metrics_policy = "warn"

    def __init__(self, weight: float = 1.0) -> None:
        # TODO(中/EN): 设置稳定组件名与说明 / set stable name and description.
        super().__init__(name="bias_template", weight=float(weight), description="TODO")

    def compute(self, x: np.ndarray, context: OptimizationContext) -> float:
        # TODO(中/EN): 返回标量偏好分 / return a scalar preference score.
        _ = x
        _ = context
        raise NotImplementedError
