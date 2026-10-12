"""可复用的候选策略；旧 demo 仅保留兼容导入。"""
from __future__ import annotations
from typing import Any, Dict, Sequence
import numpy as np
from nsgablack.adapters.candidate_proposer import CandidateProposerAdapter

class RandomProbeAdapter(CandidateProposerAdapter):
    context_requires = ()
    context_provides = ()
    context_mutates = ()
    context_cache = ()

    def __init__(self, samples=4):
        super().__init__(name='random_probe')
        self.samples = samples

    def propose(self, control, context):
        return self.build_candidate_units([control.init_candidate(context) for _ in range(self.samples)], context)

    def update(self, control, candidates, feedback, context):
        _ = (control, candidates, feedback, context)

class LocalStepAdapter(CandidateProposerAdapter):
    context_requires = ()
    context_provides = ()
    context_mutates = ()
    context_cache = ()

    def __init__(self, samples=2):
        super().__init__(name='local_step')
        self.samples = samples

    def propose(self, control, context):
        if control.best_x is None:
            return self.build_candidate_units([], context)
        return self.build_candidate_units([control.mutate_candidate(control.best_x, context) for _ in range(self.samples)], context)

    def update(self, control, candidates, feedback, context):
        _ = (control, candidates, feedback, context)
