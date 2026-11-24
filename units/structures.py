"""Small immutable structures; search decisions remain in Adapters."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, ClassVar
import numpy as np
from blackbase.types import UnknownState

from .contracts import UnitSchema, candidate_array
from .features import FeatureUnit


CANDIDATE_SCHEMA = UnitSchema("nsgablack.candidate_unit")
SEARCH_NODE_SCHEMA = UnitSchema("nsgablack.search_node", required_fields=(
    "state", "g", "h", "f", "parent_key", "parent_id",
))


@dataclass(frozen=True)
class CandidateUnit(FeatureUnit):
    unit_id: str
    candidate: Any
    schema: ClassVar[UnitSchema] = CANDIDATE_SCHEMA

    def __post_init__(self) -> None:
        values = candidate_array(self.candidate)
        if not isinstance(self.candidate, UnknownState):
            values = np.array(values, copy=True)
            values.setflags(write=False)
            object.__setattr__(self, "candidate", values)

    def to_candidate(self) -> Any:
        if isinstance(self.candidate, UnknownState):
            return self.candidate
        return np.array(self.candidate, copy=True)


@dataclass(frozen=True)
class SearchNodeUnit(CandidateUnit):
    g: float = 0.0
    h: float = 0.0
    f: float = 0.0
    parent_key: Any = None
    parent_id: str | None = None
    schema: ClassVar[UnitSchema] = SEARCH_NODE_SCHEMA

    @property
    def state(self) -> np.ndarray:
        return np.array(candidate_array(self.candidate), copy=True)


PARETO_LABEL_SCHEMA = UnitSchema("nsgablack.pareto_label", required_fields=(
    "state", "g", "h", "f", "parent_key", "parent_id", "valid",
))


@dataclass
class ParetoLabelUnit(FeatureUnit):
    unit_id: str
    candidate: Any
    g: np.ndarray
    h: np.ndarray
    f: np.ndarray
    parent_key: Any = None
    parent_id: str | None = None
    valid: bool = True
    schema: ClassVar[UnitSchema] = PARETO_LABEL_SCHEMA

    def __post_init__(self):
        self.candidate = np.array(candidate_array(self.candidate), copy=True)
        self.g, self.h, self.f = (np.array(v, dtype=float, copy=True) for v in (self.g, self.h, self.f))
        self.validate()

    def validate(self):
        if self.g.ndim != 1 or self.g.shape != self.h.shape or self.g.shape != self.f.shape:
            raise ValueError("Pareto label costs must be aligned vectors")

    @property
    def state(self):
        return self.candidate.copy()

    def to_candidate(self):
        return self.candidate.copy()
