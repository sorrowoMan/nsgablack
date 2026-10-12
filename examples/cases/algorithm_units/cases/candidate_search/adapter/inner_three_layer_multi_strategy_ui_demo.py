"""可复用的候选策略；旧 demo 仅保留兼容导入。"""
from __future__ import annotations
from typing import Any, Dict, Sequence
import numpy as np
from nsgablack.adapters.candidate_proposer import CandidateProposerAdapter

class _L3Adapter(CandidateProposerAdapter):
    context_requires = ()
    context_provides = ()
    context_mutates = ()
    context_cache = ()
    context_notes = ('Proposes target and stress-test candidate for L3.',)

    def __init__(self, target: float):
        super().__init__(name='l3_adapter')
        self.target = float(target)

    def propose(self, control, context):
        _ = (control, context)
        return self.build_candidate_units([np.array([self.target], dtype=float), np.array([9.0], dtype=float)], context)

    def update(self, control, candidates, feedback, context):
        _ = (control, candidates, feedback, context)

class _L2Explorer(CandidateProposerAdapter):
    context_requires = ()
    context_provides = ()
    context_mutates = ()
    context_cache = ()
    context_notes = ('Explorer role in L2 multi-strategy.',)

    def __init__(self):
        super().__init__(name='l2_explorer')

    def propose(self, control, context):
        _ = (control, context)
        return self.build_candidate_units([np.array([2.0], dtype=float)], context)

    def update(self, control, candidates, feedback, context):
        _ = (control, candidates, feedback, context)

class _L2Exploiter(CandidateProposerAdapter):
    context_requires = ()
    context_provides = ()
    context_mutates = ()
    context_cache = ()
    context_notes = ('Exploiter role in L2 multi-strategy.',)

    def __init__(self):
        super().__init__(name='l2_exploiter')

    def propose(self, control, context):
        _ = (control, context)
        return self.build_candidate_units([np.array([-2.0], dtype=float)], context)

    def update(self, control, candidates, feedback, context):
        _ = (control, candidates, feedback, context)

class _L1Adapter(CandidateProposerAdapter):
    context_requires = ()
    context_provides = ()
    context_mutates = ()
    context_cache = ()
    context_notes = ('Top-level adapter for L1.',)

    def __init__(self):
        super().__init__(name='l1_adapter')

    def propose(self, control, context):
        _ = (control, context)
        return self.build_candidate_units([np.array([0.0], dtype=float)], context)

    def update(self, control, candidates, feedback, context):
        _ = (control, candidates, feedback, context)
