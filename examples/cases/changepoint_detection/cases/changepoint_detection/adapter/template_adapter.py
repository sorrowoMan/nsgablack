# -*- coding: utf-8 -*-
# Adapter template: copy and customize propose/update.

from __future__ import annotations

from typing import Any, Dict, Sequence

import numpy as np

from nsgablack.adapters.algorithm_adapter import AlgorithmAdapter


class AdapterTemplate(AlgorithmAdapter):
    # Minimal runnable adapter template.

    context_requires = ()
    context_provides = ()
    context_mutates = ()
    context_cache = ()
    context_notes = ("Adapter template: manage algorithm state in propose/update.",)

    def __init__(self, max_candidates: int = 8) -> None:
        super().__init__(name="adapter_template")
        self.max_candidates = max(1, int(max_candidates))
        self._last_population: np.ndarray | None = None

    def propose(self, control: Any, context: Dict[str, Any]) -> Sequence[np.ndarray]:
        _ = context
        rng = self.create_local_rng(control)
        dim = int(getattr(getattr(control, "problem", None), "dimension", 1))
        out = []
        for _ in range(self.max_candidates):
            out.append(rng.uniform(-1.0, 1.0, size=(dim,)))
        return out

    def update(self, control: Any, candidates: Sequence[np.ndarray], feedback, context: Dict[str, Any]) -> None:
        objectives, violations = feedback
        _ = (control, objectives, violations, context)
        if candidates is not None and len(candidates) > 0:
            self._last_population = np.asarray(candidates, dtype=float)
