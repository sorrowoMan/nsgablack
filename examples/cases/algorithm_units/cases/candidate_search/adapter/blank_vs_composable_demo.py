"""可复用的候选策略；旧 demo 仅保留兼容导入。"""
from __future__ import annotations
from typing import Any, Dict, Sequence
import numpy as np
from nsgablack.adapters.candidate_proposer import CandidateProposerAdapter

class GreedyAdapter(CandidateProposerAdapter):
    context_requires = ()
    context_provides = ()
    context_mutates = ()
    context_cache = ()
    """同一策略通过 Adapter 复用 ComposableSolver 的完整提交逻辑。"""

    def __init__(self) -> None:
        super().__init__(name='greedy_adapter')

    def propose(self, control: Any, context: dict[str, Any]):
        if control.best_x is None:
            return self.build_candidate_units([control.init_candidate(context)], context)
        return self.build_candidate_units([control.mutate_candidate(control.best_x, context)], context)

    def update(self, control: Any, candidates: Any, feedback: Any, context: Any) -> None:
        _ = (control, candidates, feedback, context)
