"""候选管线只执行无变化修复，不拥有 CMA 分布或搜索决策。"""
import numpy as np
from nsgablack.representation import RepresentationPipeline


class IdentityRepair:
    """此 Case 不改变 CMA 采样分布；实际改变会由 Adapter 明确拒绝。"""
    context_requires = context_provides = context_mutates = context_cache = ()
    context_notes = "Returns a detached unchanged candidate; no shared context access."

    def repair(self, candidate, context=None):
        return np.array(candidate, dtype=float, copy=True)


def build_pipeline():
    return RepresentationPipeline(repair=IdentityRepair())
