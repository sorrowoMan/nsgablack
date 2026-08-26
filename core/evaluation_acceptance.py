"""Post-evaluation admission policies for adapter updates.

The evaluation layer may successfully produce feedback for candidates that
must not be committed to an algorithm's state.  Policies in this module make
that decision explicit and project it through the shared ``BatchDisposition``
contract so composite adapters can reconcile their child proposal ranges.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Protocol, runtime_checkable

import numpy as np

from blackbase.contracts import BatchDisposition
from blackbase.types import CandidateBatch

from .evaluation_feedback import OptimizationFeedbackBatch


@runtime_checkable
class EvaluationAcceptancePolicy(Protocol):
    """Select evaluated candidates that may enter ``Adapter.update``."""

    policy_id: str

    def select(
        self,
        candidates: CandidateBatch,
        feedback: OptimizationFeedbackBatch,
        context: Mapping[str, Any],
    ) -> BatchDisposition:
        """Return indices into the evaluated candidate batch."""


@dataclass(frozen=True)
class FeasibleEvaluationAcceptance:
    """Admit only candidates with finite violation no greater than tolerance."""

    constraint_tolerance: float = 1e-9
    policy_id: str = "feasible-evaluation/v1"

    def __post_init__(self) -> None:
        tolerance = float(self.constraint_tolerance)
        if not np.isfinite(tolerance) or tolerance < 0.0:
            raise ValueError("constraint_tolerance must be finite and >= 0")
        object.__setattr__(self, "constraint_tolerance", tolerance)
        normalized_id = str(self.policy_id or "").strip()
        if not normalized_id:
            raise ValueError("policy_id must not be empty")
        object.__setattr__(self, "policy_id", normalized_id)

    def select(
        self,
        candidates: CandidateBatch,
        feedback: OptimizationFeedbackBatch,
        context: Mapping[str, Any],
    ) -> BatchDisposition:
        del context
        proposed_count = int(candidates.numeric_matrix.shape[0])
        if feedback.candidate_count != proposed_count:
            raise ValueError(
                "acceptance policy candidate/feedback counts must match: "
                f"candidates={proposed_count}, feedback={feedback.candidate_count}"
            )
        violations = np.asarray(feedback.violations, dtype=float).reshape(-1)
        accepted = tuple(
            int(index)
            for index in np.flatnonzero(
                np.isfinite(violations)
                & (violations <= float(self.constraint_tolerance))
            )
        )
        return BatchDisposition(
            proposed_count=proposed_count,
            accepted_indices=accepted,
            reason="feasible_evaluation_filter",
            metadata={
                "policy_id": self.policy_id,
                "constraint_tolerance": float(self.constraint_tolerance),
                "rejected_nonfinite_count": int(np.sum(~np.isfinite(violations))),
            },
        )


__all__ = [
    "EvaluationAcceptancePolicy",
    "FeasibleEvaluationAcceptance",
]
