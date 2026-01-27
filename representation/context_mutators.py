"""
Context-aware mutator helpers.

These helpers allow algorithm adapters (e.g. VNS) to control operator behavior
via the shared `context` dict without hard-coding representation details into
the adapter itself.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, List, Optional

import numpy as np


@dataclass
class ContextSwitchMutator:
    """Select a mutator based on a context key (e.g. VNS neighborhood index).

    Typical usage:
      - Adapter writes `context["vns_k"] = k`
      - Pipeline uses `ContextSwitchMutator(mutators=[...], k_key="vns_k")`
    """

    mutators: List[Any]
    k_key: str = "vns_k"

    def mutate(self, x: np.ndarray, context: Optional[dict] = None) -> np.ndarray:
        if not self.mutators:
            return np.asarray(x)

        k = 0
        if context is not None:
            try:
                k = int(context.get(self.k_key, 0))
            except Exception:
                k = 0

        idx = max(0, min(k, len(self.mutators) - 1))
        mutator = self.mutators[idx]
        fn = getattr(mutator, "mutate", None)
        if not callable(fn):
            raise TypeError(f"ContextSwitchMutator mutator[{idx}] has no callable mutate()")
        return np.asarray(fn(np.asarray(x), context))

