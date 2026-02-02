"""
Dynamic pipeline helpers (stage-based repair switching).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Sequence, Tuple, Any


@dataclass
class DynamicRepair:
    """
    Switch repair operators by generation.

    stages: list of (start_generation, repair_plugin)
    """

    stages: Sequence[Tuple[int, Any]]

    def __init__(self, stages: Sequence[Tuple[int, Any]]) -> None:
        self.stages = sorted([(int(s), r) for s, r in stages], key=lambda x: x[0])

    def repair(self, x: Any, context: Optional[dict] = None) -> Any:
        gen = 0
        if context is not None:
            try:
                gen = int(context.get("generation", 0))
            except Exception:
                gen = 0
        chosen = None
        for start, rep in self.stages:
            if gen >= start:
                chosen = rep
            else:
                break
        if chosen is None:
            return x
        return chosen.repair(x, context)
