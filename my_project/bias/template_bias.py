# -*- coding: utf-8 -*-
"""偏置模板：复制后改文件名和类名即可接入。"""

from __future__ import annotations

import numpy as np

from nsgablack.bias.core.base import BiasBase, OptimizationContext


class BiasTemplate(BiasBase):
    """最小可运行偏置模板。"""

    context_requires = ()
    context_provides = ()
    context_mutates = ()
    context_cache = ()
    context_notes = ("偏置模板：基于 x/context 计算一个标量偏好值。",)
    requires_metrics = ()
    metrics_fallback = "none"
    missing_metrics_policy = "warn"

    def __init__(self, weight: float = 1.0) -> None:
        # weight 控制偏置强度；建议先用 1.0 再微调
        super().__init__(name="bias_template", weight=float(weight), description="偏置模板")

    def compute(self, x: np.ndarray, context: OptimizationContext) -> float:
        # 返回值越大表示越偏好；这里默认返回 0（不施加偏好）
        _ = context
        _ = x
        return 0.0
