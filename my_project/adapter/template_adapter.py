# -*- coding: utf-8 -*-
"""Adapter template / 适配器模板。"""

from __future__ import annotations

from nsgablack.catalog.markers import component
from nsgablack.core.adapters.algorithm_adapter import AlgorithmAdapter


@component(kind="adapter")
class AdapterTemplate(AlgorithmAdapter):
    # TODO(中/EN): 仅声明真实读写字段 / declare only real read-write fields.
    context_requires = ()
    context_provides = ()
    context_mutates = ()
    context_cache = ()
    context_notes = ("TODO(中/EN): 一句话说明 context 契约 / one-line context contract.",)

    def __init__(self) -> None:
        # TODO(中/EN): 设置稳定适配器名 / set a stable adapter name.
        super().__init__(name="adapter_template")

    def propose(self, solver, context):
        # TODO(中/EN): 生成候选解 / generate candidate solutions.
        _ = solver
        _ = context
        raise NotImplementedError

    def update(self, solver, candidates, objectives, violations, context):
        # TODO(中/EN): 用评估反馈更新状态 / update state with evaluation feedback.
        _ = solver
        _ = candidates
        _ = objectives
        _ = violations
        _ = context
        raise NotImplementedError
