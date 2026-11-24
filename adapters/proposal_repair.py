"""Pre-evaluation repair evidence in an Adapter's original proposal coordinates."""
from __future__ import annotations

from dataclasses import dataclass
import json

import numpy as np
from blackbase.contracts import BatchDisposition
from blackbase.types import CandidateBatch


@dataclass(frozen=True)
class ProposalRepair:
    """Same-identity transformation, distinct from an admission disposition.

    Only budget-approved rows need appear. ``proposal_indices`` addresses the
    owner's full pending proposal list, before any disposition has compacted it.
    CandidateBatch detaches values/metadata, including before in-place repair.
    """

    context_requires = ()
    context_provides = ()
    context_mutates = ()
    context_cache = ()
    context_notes = "Detached repair value; does not read or write shared context keys."

    proposed_count: int
    proposal_indices: tuple[int, ...]
    before: CandidateBatch
    after: CandidateBatch

    def __post_init__(self) -> None:
        indices = tuple(self.proposal_indices)
        if type(self.proposed_count) is not int or self.proposed_count < 0:
            raise ValueError("repair proposed_count must be a nonnegative integer")
        if any(type(i) is not int or not 0 <= i < self.proposed_count for i in indices):
            raise ValueError("repair indices must address original proposals")
        if tuple(sorted(set(indices))) != indices:
            raise ValueError("repair indices must be unique and ordered")
        if not isinstance(self.before, CandidateBatch) or not isinstance(self.after, CandidateBatch):
            raise TypeError("repair evidence requires CandidateBatch values")
        if (len(indices) != len(self.before.semantic_states)
                or self.before.numeric_matrix.shape != self.after.numeric_matrix.shape):
            raise ValueError("repair must preserve row count and dimension")
        tokens = self.before.candidate_tokens
        if (tokens != self.after.candidate_tokens or any(t is None for t in tokens)
                or len(set(tokens)) != len(tokens)):
            raise ValueError("repair must preserve aligned, unique candidate tokens")
        object.__setattr__(self, "proposal_indices", indices)

    @property
    def changed_rows(self) -> tuple[int, ...]:
        # Metadata is semantic: a numeric no-op can still change the candidate.
        return tuple(i for i, (before, after) in enumerate(zip(
            self.before.semantic_states, self.after.semantic_states
        )) if not np.array_equal(before.values, after.values, equal_nan=True)
            or json.dumps(before.as_dict()["metadata"], sort_keys=True)
            != json.dumps(after.as_dict()["metadata"], sort_keys=True))

    @property
    def changed_indices(self) -> tuple[int, ...]:
        return tuple(self.proposal_indices[i] for i in self.changed_rows)

    def for_range(self, start: int, end: int) -> "ProposalRepair":
        if not 0 <= start <= end <= self.proposed_count:
            raise ValueError("repair child range lies outside proposals")
        rows = tuple(i for i, index in enumerate(self.proposal_indices) if start <= index < end)
        return type(self)(end - start, tuple(self.proposal_indices[i] - start for i in rows),
                          self.before.subset(rows), self.after.subset(rows))

    def through(self, disposition: BatchDisposition | None) -> "ProposalRepair":
        """Undo a wrapper's local selection without delivering a disposition."""
        if disposition is None:
            return self
        if disposition.accepted_count != self.proposed_count:
            raise ValueError("repair does not match wrapper proposal selection")
        return type(self)(disposition.proposed_count,
                          tuple(disposition.accepted_indices[i] for i in self.proposal_indices),
                          self.before, self.after)
