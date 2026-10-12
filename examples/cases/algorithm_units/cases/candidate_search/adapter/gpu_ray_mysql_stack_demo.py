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

    def __init__(self, name: str='random_search_adapter', seed: int=7) -> None:
        super().__init__(name=name)
        self.rng = np.random.default_rng(int(seed))

    def propose(self, control: Any, context: Dict[str, Any]) -> Sequence[np.ndarray]:
        _ = context
        out = []
        lows = np.array([control.var_bounds[f'x{i}'][0] for i in range(control.dimension)], dtype=float)
        highs = np.array([control.var_bounds[f'x{i}'][1] for i in range(control.dimension)], dtype=float)
        for _ in range(int(getattr(control, 'pop_size', 32))):
            out.append(self.rng.uniform(lows, highs).astype(float))
        return self.build_candidate_units(out, context)

    def update(self, control: Any, candidates, feedback, context: Dict[str, Any]) -> None:
        objectives, violations = feedback
        _ = (control, candidates, objectives, violations, context)
        return None
