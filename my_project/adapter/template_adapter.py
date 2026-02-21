# -*- coding: utf-8 -*-
"""适配器模板：复制后改文件名和类名即可接入 propose/update 流程。"""

from __future__ import annotations

from typing import Any, Dict, Sequence

import numpy as np

from nsgablack.core.adapters.algorithm_adapter import AlgorithmAdapter


class AdapterTemplate(AlgorithmAdapter):
    """最小可运行适配器模板。"""

    context_requires = ()
    context_provides = ()
    context_mutates = ()
    context_cache = ()
    context_notes = ("适配器模板：在 propose/update 生命周期中维护算法状态。",)

    def __init__(self, max_candidates: int = 8) -> None:
        super().__init__(name="adapter_template")
        # 每轮最多提出多少个候选解
        self.max_candidates = max(1, int(max_candidates))
        self._last_population: np.ndarray | None = None

    def propose(self, solver: Any, context: Dict[str, Any]) -> Sequence[np.ndarray]:
        # 提案阶段：生成候选解列表
        _ = context
        rng = self.create_local_rng(solver)
        dim = int(getattr(getattr(solver, "problem", None), "dimension", 1))
        out = []
        for _ in range(self.max_candidates):
            out.append(rng.uniform(-1.0, 1.0, size=(dim,)))
        return out

    def update(
        self,
        solver: Any,
        candidates: Sequence[np.ndarray],
        objectives: np.ndarray,
        violations: np.ndarray,
        context: Dict[str, Any],
    ) -> None:
        # 更新阶段：消费评估反馈，维护内部状态
        _ = solver
        _ = objectives
        _ = violations
        _ = context
        if candidates:
            self._last_population = np.asarray(candidates, dtype=float)
