# -*- coding: utf-8 -*-
# Example adapter (simple random proposer).

from __future__ import annotations

from typing import Any, Dict, Sequence

import numpy as np

from nsgablack.adapters.candidate_proposer import CandidateProposerAdapter


class ExampleAdapter(CandidateProposerAdapter):
    def __init__(self, max_candidates: int = 8, seed: int = 0, *, unit_binding=None) -> None:
        super().__init__(name="example_adapter", unit_binding=unit_binding)
        self.max_candidates = max(1, int(max_candidates))
        self._rng = np.random.default_rng(int(seed))

    def propose(self, control: Any, context: Dict[str, Any]) -> Sequence[np.ndarray]:
        _ = context
        dim = int(getattr(getattr(control, "problem", None), "dimension", 1))
        out = []
        for _ in range(self.max_candidates):
            out.append(self._rng.uniform(-1.0, 1.0, size=(dim,)))
        return self.build_candidate_units(out, context)

    def update(
        self,
        control: Any,
        candidates: Sequence[np.ndarray],
        feedback,
        context: Dict[str, Any],
    ) -> None:
        """Accept evaluation feedback; the proposer keeps its Unit and RNG checkpoint in the base class."""

        _ = (control, candidates, feedback, context)
