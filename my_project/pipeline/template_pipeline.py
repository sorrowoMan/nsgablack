# -*- coding: utf-8 -*-
"""管线模板：复制后改类名即可组合 initializer/mutator/repair。"""

from __future__ import annotations

from typing import Optional

import numpy as np

from nsgablack.representation.base import RepresentationComponentContract


class PipelineInitializerTemplate(RepresentationComponentContract):
    """初始化器模板。"""

    context_requires = ()
    context_provides = ()
    context_mutates = ()
    context_cache = ()
    context_notes = ("初始化器模板：负责生成可行初始解。",)

    def initialize(self, problem, context: Optional[dict] = None) -> np.ndarray:
        # 这里默认全零初始化；按你的问题改成随机或启发式都可以
        _ = context
        return np.zeros(problem.dimension, dtype=float)


class PipelineMutationTemplate(RepresentationComponentContract):
    """变异器模板。"""

    context_requires = ()
    context_provides = ()
    context_mutates = ()
    context_cache = ()
    context_notes = ("变异器模板：输入 x 输出 x'。",)

    def mutate(self, x: np.ndarray, context: Optional[dict] = None) -> np.ndarray:
        # 这里是无操作变异；先保证流程通，再换成真实变异
        _ = context
        return np.array(x, copy=True)


class PipelineRepairTemplate(RepresentationComponentContract):
    """修复器模板。"""

    context_requires = ()
    context_provides = ()
    context_mutates = ()
    context_cache = ()
    context_notes = ("修复器模板：把候选解拉回可行域。",)

    def repair(self, x: np.ndarray, context: Optional[dict] = None) -> np.ndarray:
        # 这里默认不改动；后续按硬约束补修复逻辑
        _ = context
        return np.array(x, copy=True)
