"""可复用的候选策略；旧 demo 仅保留兼容导入。"""
from __future__ import annotations
from typing import Any, Dict, Sequence
import numpy as np
from nsgablack.adapters.candidate_proposer import CandidateProposerAdapter

class FixedAdapter(CandidateProposerAdapter):
    context_requires = ()
    context_provides = ()
    context_mutates = ()
    context_cache = ()
    context_notes = ('Proposes fixed candidate for ngspice inner demo.',)

    def __init__(self) -> None:
        super().__init__(name='fixed_adapter')

    def propose(self, control, context):
        _ = (control, context)
        return self.build_candidate_units([np.array([2.0], dtype=float)], context)

    def update(self, control, candidates, feedback, context):
        _ = (control, candidates, feedback, context)
