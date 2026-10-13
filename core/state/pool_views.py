"""Portable objective projections attached to candidate-reference subpools."""
from __future__ import annotations

from dataclasses import dataclass, replace

import numpy as np

from ..evaluation_feedback import OptimizationFeedbackBatch, copy_feedback_with_result


@dataclass(frozen=True)
class ObjectiveProjection:
    """A fixed comparison frame; raw evaluation and constraints remain intact."""

    method: str
    weights: tuple[float, ...]
    reference: tuple[float, ...] = ()

    def __post_init__(self):
        object.__setattr__(self, "weights", tuple(float(v) for v in self.weights))
        object.__setattr__(self, "reference", tuple(float(v) for v in self.reference))
        if self.method not in {"weighted_sum", "tchebycheff"}:
            raise ValueError("unsupported subpool objective projection")
        w = np.asarray(self.weights)
        if not len(w) or not np.all(np.isfinite(w)) or np.any(w < 0) or not np.any(w > 0):
            raise ValueError("projection weights must be finite nonnegative values with positive mass")
        if self.method == "tchebycheff":
            if len(self.reference) != len(w) or not np.all(np.isfinite(self.reference)):
                raise ValueError("Tchebycheff projection needs an aligned finite reference")
        elif self.reference:
            raise ValueError("weighted-sum projection does not use a reference")

    def as_dict(self):
        return dict(method=self.method, weights=list(self.weights), reference=list(self.reference))

    @classmethod
    def from_dict(cls, value):
        if not isinstance(value, dict) or set(value) != {"method", "weights", "reference"}:
            raise ValueError("invalid subpool projection descriptor")
        return cls(**value)

    def apply(self, feedback):
        feedback = OptimizationFeedbackBatch.coerce(feedback)
        values = feedback.objectives
        if values.shape[1] != len(self.weights):
            raise ValueError("subpool projection objective dimension mismatch")
        if self.method == "weighted_sum":
            scores = values @ np.asarray(self.weights)
        else:
            scores = np.max(np.abs(values - np.asarray(self.reference)) * self.weights, axis=1)
        items = []
        raw_f, raw_v = feedback.raw_objectives, feedback.raw_violations
        for i, item in enumerate(feedback.items):
            copied = copy_feedback_with_result(item, objectives=[scores[i]], violation=feedback.violations[i])
            # with_arrays alone cannot preserve raw evidence for unbiased batches.
            info = dict(copied.info)
            info.setdefault("raw_evaluation", dict(objectives=raw_f[i].tolist(),
                constraint_violation=float(raw_v[i])))
            items.append(replace(copied, info=info))
        return OptimizationFeedbackBatch.from_feedback(items, violations=feedback.violations,
            metadata={**dict(feedback.metadata), "subpool_projection": self.as_dict(),
                      "constraint_order": "feasibility_first"})


__all__ = ["ObjectiveProjection"]
