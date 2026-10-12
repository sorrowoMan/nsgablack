"""Explicit row provenance for Unit maintenance after an Adapter decision."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

import numpy as np


@dataclass(frozen=True)
class PopulationChange:
    """One final row comes from a previous member or an incoming row.

    Indices describe structural provenance, never numeric equality. Repeated
    incoming indices allow one proposal to occupy several decomposition slots.
    This call-local value is not a checkpoint or an acceptance disposition.
    """

    operation: str
    previous_count: int
    incoming_count: int
    previous_member_indices: tuple[int | None, ...]
    incoming_member_indices: tuple[int | None, ...]
    incoming_population: Any = field(default=None, kw_only=True, repr=False, compare=False)
    incoming_objectives: Any = field(default=None, kw_only=True, repr=False, compare=False)
    incoming_violations: Any = field(default=None, kw_only=True, repr=False, compare=False)
    incoming_tokens: tuple[str | None, ...] = field(default=(), kw_only=True)
    incoming_metadata: tuple[Mapping[str, Any], ...] = field(default=(), kw_only=True, repr=False, compare=False)
    incoming_provenance: tuple[Mapping[str, Any] | None, ...] = field(default=(), kw_only=True, repr=False, compare=False)

    def __post_init__(self):
        if self.operation not in {"initialize", "selection", "replacement", "clear"}:
            raise ValueError("Unknown population member operation")
        for count in (self.previous_count, self.incoming_count):
            if type(count) is not int or count < 0:
                raise ValueError("Population member counts must be nonnegative integers")
        old, new = tuple(self.previous_member_indices), tuple(self.incoming_member_indices)
        if len(old) != len(new):
            raise ValueError("Population member source maps must align")
        for before, incoming in zip(old, new):
            if (before is None) == (incoming is None):
                raise ValueError("Each population row needs exactly one source")
            for index, count in ((before, self.previous_count), (incoming, self.incoming_count)):
                if index is not None and (type(index) is not int or not 0 <= index < count):
                    raise ValueError("Population member source index is out of range")
        object.__setattr__(self, "previous_member_indices", old)
        object.__setattr__(self, "incoming_member_indices", new)
        # Inputs are call-local, detached and immutable. Existing index-only
        # construction remains valid; structural operations always supply data.
        from .features import _snapshot
        x, f, v = self.incoming_population, self.incoming_objectives, self.incoming_violations
        if x is not None:
            x = np.asarray(x, dtype=float)
            if x.ndim != 2 or len(x) != self.incoming_count:
                raise ValueError("PopulationChange incoming population must align with incoming_count")
        if (f is None) != (v is None) or (f is not None and x is None):
            raise ValueError("PopulationChange incoming feedback requires paired, aligned candidates")
        if f is not None:
            f, v = np.asarray(f, dtype=float), np.asarray(v, dtype=float)
            if f.ndim != 2 or len(f) != self.incoming_count or v.shape != (self.incoming_count,):
                raise ValueError("PopulationChange incoming feedback must align with incoming_count")
        tokens = tuple(self.incoming_tokens)
        metadata, provenance = tuple(self.incoming_metadata), tuple(self.incoming_provenance)
        if x is not None:
            tokens = tokens or (None,) * self.incoming_count
            metadata = metadata or tuple({} for _ in range(self.incoming_count))
            provenance = provenance or (None,) * self.incoming_count
        if ((tokens and len(tokens) != self.incoming_count)
                or any(t is not None and (not isinstance(t, str) or not t) for t in tokens)
                or (metadata and len(metadata) != self.incoming_count)
                or any(not isinstance(m, Mapping) for m in metadata)
                or (provenance and len(provenance) != self.incoming_count)
                or any(p is not None and not isinstance(p, Mapping) for p in provenance)):
            raise ValueError("PopulationChange incoming identities and metadata must align")
        for token, record in zip(tokens, provenance):
            if record is not None and record.get("candidate_token") != token:
                raise ValueError("PopulationChange provenance disagrees with candidate token")
        _, data = _snapshot(dict(population=x, objectives=f, violations=v, tokens=tokens,
                                 metadata=metadata, provenance=provenance))
        for name, value in data.items():
            object.__setattr__(self, "incoming_" + name, value)

    @property
    def count(self) -> int:
        return len(self.previous_member_indices)
