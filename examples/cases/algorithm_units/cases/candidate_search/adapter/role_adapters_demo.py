"""可复用的候选策略；旧 demo 仅保留兼容导入。"""
from __future__ import annotations
from typing import Any, Dict, Sequence
import numpy as np
from nsgablack.adapters.candidate_proposer import CandidateProposerAdapter

class Explorer(CandidateProposerAdapter):
    context_requires = ()
    context_provides = ()
    context_mutates = ()
    context_cache = ()

    def __init__(self):
        super().__init__(name='explorer')

    def propose(self, control, context):
        return self.build_candidate_units([control.mutate_candidate(control.init_candidate(context), context) for _ in range(12)], context)

    def update(self, control, candidates, feedback, context):
        _ = (control, candidates, feedback, context)

class Exploiter(CandidateProposerAdapter):
    context_requires = ()
    context_provides = ()
    context_mutates = ()
    context_cache = ()

    def __init__(self):
        super().__init__(name='exploiter')

    def propose(self, control, context):
        if control.best_x is None:
            return self.build_candidate_units([control.init_candidate(context) for _ in range(8)], context)
        return self.build_candidate_units([control.mutate_candidate(control.best_x, context) for _ in range(8)], context)

    def update(self, control, candidates, feedback, context):
        _ = (control, candidates, feedback, context)
