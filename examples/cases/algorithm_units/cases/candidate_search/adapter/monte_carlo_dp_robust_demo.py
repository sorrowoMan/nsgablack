"""可复用的候选策略；旧 demo 仅保留兼容导入。"""
from __future__ import annotations
from typing import Any, Dict, Sequence
import numpy as np
from nsgablack.adapters.candidate_proposer import CandidateProposerAdapter

class FixedPathAdapter(CandidateProposerAdapter):
    context_requires = ()
    context_provides = ()
    context_mutates = ()
    context_cache = ()

    def __init__(self, path: np.ndarray, name: str) -> None:
        super().__init__(name=name)
        self.path = np.asarray(path, dtype=float)

    def propose(self, control, context):
        return self.build_candidate_units([self.path], context)

    def update(self, control, candidates, feedback, context):
        _ = (control, candidates, feedback, context)
