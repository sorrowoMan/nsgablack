"""Explicit row provenance for Unit maintenance after an Adapter decision."""
from __future__ import annotations

from dataclasses import dataclass


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

    @property
    def count(self) -> int:
        return len(self.previous_member_indices)
