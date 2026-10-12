"""可复用的候选策略；旧 demo 仅保留兼容导入。"""
from __future__ import annotations
from typing import Any, Dict, Sequence
import numpy as np
from nsgablack.adapters.candidate_proposer import CandidateProposerAdapter

class RandomSearchAdapter(CandidateProposerAdapter):
    context_requires = ()
    context_provides = ()
    context_mutates = ()
    context_cache = ()

    def __init__(self) -> None:
        super().__init__(name='random_search')
        self.rng = np.random.default_rng(7)

    def propose(self, control, context):
        _ = context
        low, high = (-2.0, 2.0)
        out = []
        for _ in range(int(getattr(control, 'pop_size', 8))):
            out.append(np.array([float(self.rng.uniform(low, high))], dtype=float))
        return self.build_candidate_units(out, context)

    def update(self, control, candidates, feedback, context):
        _ = (control, candidates, feedback, context)
