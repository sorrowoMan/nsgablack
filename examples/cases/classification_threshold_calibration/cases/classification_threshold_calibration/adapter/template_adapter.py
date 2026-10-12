# -*- coding: utf-8 -*-
# Adapter template: copy and customize propose/update.

from __future__ import annotations

from typing import Any, Dict, Sequence

import numpy as np

from nsgablack.adapters.candidate_proposer import CandidateProposerAdapter


class AdapterTemplate(CandidateProposerAdapter):
    # Minimal runnable adapter template.

    context_requires = ()
    context_provides = ()
    context_mutates = ()
    context_cache = ()
    context_notes = ("Adapter template: manage algorithm state in propose/update.",)

    def __init__(self, max_candidates: int = 8, *, unit_binding=None) -> None:
        super().__init__(name="adapter_template", unit_binding=unit_binding)
        self.max_candidates = max(1, int(max_candidates))

    def propose(self, control: Any, context: Dict[str, Any]) -> Sequence[np.ndarray]:
        _ = context
        rng = self.create_local_rng(control)
        dim = int(getattr(getattr(control, "problem", None), "dimension", 1))
        out = []
        for _ in range(self.max_candidates):
            out.append(rng.uniform(-1.0, 1.0, size=(dim,)))
        return self.build_candidate_units(out, context)

    def update(self, control: Any, candidates: Sequence[np.ndarray], feedback, context: Dict[str, Any]) -> None:
        objectives, violations = feedback
        _ = (control, objectives, violations, context)
        # 最近提案保存在 proposal_units；它不是 L2 权威种群。
