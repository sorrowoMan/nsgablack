"""
Structure prior bias (symmetry/group structure).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, List, Optional, Sequence, Tuple
import numpy as np

from ..core.base import DomainBias, OptimizationContext


@dataclass
class StructurePriorBias(DomainBias):
    """
    Penalize deviations from a structural prior.

    Supported modes:
    - "pair": penalize |x[i]-x[j]| across index pairs
    - "group": penalize variance within groups of indices
    - "custom": user provides a callable via custom_penalty
    """
    context_requires = ("problem_data",)
    context_provides = ()
    context_mutates = ()
    context_cache = ()
    context_notes = "Reads context fields: problem_data; outputs scalar bias only."



    pairs: Optional[Sequence[Tuple[int, int]]] = None
    groups: Optional[Sequence[Sequence[int]]] = None
    mode: str = "pair"
    custom_penalty: Optional[Any] = None

    def __init__(
        self,
        name: str = "structure_prior",
        *,
        pairs: Optional[Sequence[Tuple[int, int]]] = None,
        groups: Optional[Sequence[Sequence[int]]] = None,
        weight: float = 1.0,
        mode: str = "pair",
        custom_penalty: Optional[Any] = None,
        mandatory: bool = False,
    ) -> None:
        super().__init__(name=name, weight=weight, mandatory=mandatory)
        self.pairs = pairs
        self.groups = groups
        self.mode = str(mode or "pair").lower().strip()
        self.custom_penalty = custom_penalty

    def compute(self, x: np.ndarray, context: OptimizationContext) -> float:
        arr = np.asarray(x, dtype=float).ravel()
        if self.mode == "custom" and callable(self.custom_penalty):
            try:
                return float(self.custom_penalty(arr, context))
            except Exception:
                return 0.0

        if self.mode == "group" and self.groups:
            return float(self._group_variance(arr, self.groups))

        if self.pairs:
            return float(self._pair_penalty(arr, self.pairs))

        return 0.0

    @staticmethod
    def _pair_penalty(x: np.ndarray, pairs: Sequence[Tuple[int, int]]) -> float:
        total = 0.0
        for i, j in pairs:
            if i < 0 or j < 0 or i >= x.size or j >= x.size:
                continue
            total += abs(float(x[i]) - float(x[j]))
        return total

    @staticmethod
    def _group_variance(x: np.ndarray, groups: Sequence[Sequence[int]]) -> float:
        total = 0.0
        for group in groups:
            idx = [int(i) for i in group if 0 <= int(i) < x.size]
            if not idx:
                continue
            vals = x[idx]
            total += float(np.var(vals))
        return total
