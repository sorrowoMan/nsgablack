"""Rich optimization feedback carried through the Solver/Adapter boundary.

``blackbase.types.Feedback`` describes the semantic result for one evaluated
state.  NSGABlack additionally needs a population-shaped, authoritative
constraint-violation vector for selection.  ``OptimizationFeedbackBatch``
joins those two views without teaching the optimization core what gradients,
losses, residuals, or provider-specific signals mean.

The object intentionally supports legacy two-value unpacking::

    objectives, violations = feedback

Existing optimization adapters therefore keep working, while ML-aware or
domain-aware adapters can consume ``feedback.items``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, Iterator, Mapping, Sequence

import numpy as np
from blackbase.types import Feedback


def _readonly_array(value: Any, *, ndim: int | None = None) -> np.ndarray:
    array = np.array(value, dtype=float, copy=True)
    if ndim is not None and array.ndim != ndim:
        raise ValueError(f"expected a {ndim}-D array, got shape={array.shape}")
    array.setflags(write=False)
    return array


def feedback_constraint_violation(feedback: Feedback) -> float:
    """Project one semantic Feedback object onto NSGABlack violation scalar."""

    info = dict(feedback.info or {})
    for key in ("constraint_violation", "violation"):
        if key not in info or info[key] is None:
            continue
        value = float(info[key])
        if np.isfinite(value):
            return max(0.0, value)
        return value
    constraints = np.asarray(feedback.constraints, dtype=float).reshape(-1)
    if constraints.size == 0:
        return 0.0
    return float(np.sum(np.maximum(0.0, constraints)))


def copy_feedback_with_result(
    feedback: Feedback,
    *,
    objectives: Any,
    violation: float,
) -> Feedback:
    """Detach a Feedback item and replace only its optimization projection."""

    info = dict(feedback.info or {})
    info["constraint_violation"] = float(violation)
    return Feedback(
        objectives=np.array(objectives, dtype=float, copy=True).reshape(-1),
        constraints=np.array(feedback.constraints, dtype=float, copy=True).reshape(-1),
        gradients=(
            None
            if feedback.gradients is None
            else np.array(feedback.gradients, dtype=float, copy=True)
        ),
        loss=None if feedback.loss is None else float(feedback.loss),
        metrics=dict(feedback.metrics or {}),
        residuals=(
            None
            if feedback.residuals is None
            else np.array(feedback.residuals, dtype=float, copy=True)
        ),
        signals=dict(feedback.signals or {}),
        info=info,
        gradient_ref=feedback.gradient_ref,
    )


def coerce_individual_feedback(
    value: Any,
    *,
    default_violation: float = 0.0,
) -> tuple[Feedback, float]:
    """Normalize rich and legacy single-candidate evaluation results."""

    if isinstance(value, OptimizationFeedbackBatch):
        if value.candidate_count != 1:
            raise ValueError(
                "individual evaluation requires exactly one feedback item, "
                f"got {value.candidate_count}"
            )
        return value.items[0], float(value.violations[0])

    explicit_violation: float | None = None
    payload = value
    if isinstance(value, tuple) and len(value) == 2:
        first, raw_violation = value
        # A two-objective Problem may legitimately return ``(f1, f2)``.
        # Treat the pair as (objectives, violation) only when the first value
        # is itself a structured objective payload or a rich Feedback object.
        if isinstance(first, Feedback) or not np.isscalar(first):
            payload = first
            explicit_violation = float(raw_violation)

    if isinstance(payload, Feedback):
        violation = feedback_constraint_violation(payload)
        if explicit_violation is not None:
            if np.isfinite(violation) and np.isfinite(explicit_violation):
                violation = max(float(violation), float(explicit_violation))
            else:
                violation = float(explicit_violation)
        return copy_feedback_with_result(
            payload,
            objectives=payload.objectives,
            violation=violation,
        ), float(violation)

    violation = float(default_violation if explicit_violation is None else explicit_violation)
    feedback = Feedback(
        objectives=np.asarray(payload, dtype=float).reshape(-1),
        info={"constraint_violation": violation},
    )
    return feedback, violation


@dataclass(frozen=True)
class OptimizationFeedbackBatch:
    """Population feedback with both optimization and semantic projections."""

    objectives: np.ndarray
    violations: np.ndarray
    items: tuple[Feedback, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        objectives = np.asarray(self.objectives, dtype=float)
        violations = np.asarray(self.violations, dtype=float).reshape(-1)
        if objectives.ndim == 1:
            if violations.size == 1:
                objectives = objectives.reshape(1, -1)
            elif objectives.size == violations.size:
                objectives = objectives.reshape(-1, 1)
        if objectives.ndim != 2:
            raise ValueError(
                "feedback objectives must have shape (N, M), "
                f"got {objectives.shape}"
            )
        if objectives.shape[0] != violations.shape[0]:
            raise ValueError(
                "feedback objective and violation counts must match: "
                f"objectives={objectives.shape[0]}, violations={violations.shape[0]}"
            )

        raw_items = tuple(self.items or ())
        if raw_items and len(raw_items) != objectives.shape[0]:
            raise ValueError(
                "feedback item count must match objective rows: "
                f"items={len(raw_items)}, objectives={objectives.shape[0]}"
            )
        if not raw_items:
            raw_items = tuple(
                Feedback(
                    objectives=np.array(objectives[index], dtype=float, copy=True),
                    info={"constraint_violation": float(violations[index])},
                )
                for index in range(objectives.shape[0])
            )

        normalized_items: list[Feedback] = []
        for index, item in enumerate(raw_items):
            if not isinstance(item, Feedback):
                raise TypeError(
                    "feedback items must be blackbase.types.Feedback instances, "
                    f"got {type(item).__name__} at index {index}"
                )
            item_objectives = np.asarray(item.objectives, dtype=float).reshape(-1)
            expected = np.asarray(objectives[index], dtype=float).reshape(-1)
            if item_objectives.shape != expected.shape or not np.allclose(
                item_objectives,
                expected,
                equal_nan=True,
            ):
                raise ValueError(
                    f"feedback item {index} objectives do not match batch objectives"
                )
            normalized_items.append(
                copy_feedback_with_result(
                    item,
                    objectives=expected,
                    violation=float(violations[index]),
                )
            )

        object.__setattr__(self, "objectives", _readonly_array(objectives, ndim=2))
        object.__setattr__(self, "violations", _readonly_array(violations, ndim=1))
        object.__setattr__(self, "items", tuple(normalized_items))
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata or {})))

    @property
    def candidate_count(self) -> int:
        return int(self.objectives.shape[0])

    def __iter__(self) -> Iterator[np.ndarray]:
        """Preserve ``objectives, violations = feedback`` compatibility."""

        yield self.objectives
        yield self.violations

    def __len__(self) -> int:
        """Return the legacy pair arity; use candidate_count for batch size."""

        return 2

    def __getitem__(self, index: int) -> np.ndarray:
        if index == 0 or index == -2:
            return self.objectives
        if index == 1 or index == -1:
            return self.violations
        raise IndexError(index)

    @classmethod
    def from_feedback(
        cls,
        items: Sequence[Feedback],
        *,
        violations: Any | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> "OptimizationFeedbackBatch":
        normalized = tuple(items)
        if normalized:
            objectives = np.vstack(
                [np.asarray(item.objectives, dtype=float).reshape(-1) for item in normalized]
            )
        else:
            objectives = np.empty((0, 0), dtype=float)
        if violations is None:
            violations = np.asarray(
                [feedback_constraint_violation(item) for item in normalized],
                dtype=float,
            )
        return cls(
            objectives=objectives,
            violations=violations,
            items=normalized,
            metadata=dict(metadata or {}),
        )

    @classmethod
    def from_arrays(
        cls,
        objectives: Any,
        violations: Any,
        *,
        items: Sequence[Feedback] | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> "OptimizationFeedbackBatch":
        return cls(
            objectives=np.asarray(objectives, dtype=float),
            violations=np.asarray(violations, dtype=float),
            items=tuple(items or ()),
            metadata=dict(metadata or {}),
        )

    @classmethod
    def coerce(
        cls,
        value: Any,
        *,
        metadata: Mapping[str, Any] | None = None,
    ) -> "OptimizationFeedbackBatch":
        if isinstance(value, cls):
            return value
        if isinstance(value, Feedback):
            return cls.from_feedback((value,), metadata=metadata)
        if isinstance(value, Sequence) and not isinstance(
            value,
            (str, bytes, np.ndarray),
        ):
            values = tuple(value)
            if all(isinstance(item, Feedback) for item in values):
                return cls.from_feedback(values, metadata=metadata)
        if isinstance(value, tuple) and len(value) == 2:
            objectives, violations = value
            if isinstance(objectives, Feedback):
                return cls.from_feedback(
                    (objectives,),
                    violations=np.asarray((violations,), dtype=float),
                    metadata=metadata,
                )
            if isinstance(objectives, Sequence) and not isinstance(
                objectives,
                (str, bytes, np.ndarray),
            ):
                feedback_items = tuple(objectives)
                if feedback_items and all(
                    isinstance(item, Feedback) for item in feedback_items
                ):
                    return cls.from_feedback(
                        feedback_items,
                        violations=violations,
                        metadata=metadata,
                    )
            return cls.from_arrays(
                objectives,
                violations,
                metadata=metadata,
            )
        raise TypeError(
            "population evaluation must return OptimizationFeedbackBatch, a "
            "sequence of Feedback, or (objectives, violations)"
        )

    def with_arrays(
        self,
        objectives: Any,
        violations: Any,
        *,
        metadata: Mapping[str, Any] | None = None,
    ) -> "OptimizationFeedbackBatch":
        new_objectives = np.asarray(objectives, dtype=float)
        new_violations = np.asarray(violations, dtype=float).reshape(-1)
        if new_objectives.ndim == 1 and self.candidate_count == 1:
            new_objectives = new_objectives.reshape(1, -1)
        if new_objectives.shape[0] != self.candidate_count:
            raise ValueError("replacement objectives changed feedback batch cardinality")
        if new_violations.shape[0] != self.candidate_count:
            raise ValueError("replacement violations changed feedback batch cardinality")
        items = tuple(
            copy_feedback_with_result(
                self.items[index],
                objectives=new_objectives[index],
                violation=float(new_violations[index]),
            )
            for index in range(self.candidate_count)
        )
        next_metadata = dict(self.metadata)
        next_metadata.update(dict(metadata or {}))
        return type(self)(
            objectives=new_objectives,
            violations=new_violations,
            items=items,
            metadata=next_metadata,
        )

    def subset(self, selector: slice | Sequence[int] | np.ndarray) -> "OptimizationFeedbackBatch":
        indices = np.arange(self.candidate_count)[selector]
        indices = np.asarray(indices, dtype=int).reshape(-1)
        return type(self)(
            objectives=self.objectives[indices],
            violations=self.violations[indices],
            items=tuple(self.items[int(index)] for index in indices),
            metadata=dict(self.metadata),
        )


AdapterFeedback = OptimizationFeedbackBatch | tuple[np.ndarray, np.ndarray]


__all__ = [
    "AdapterFeedback",
    "OptimizationFeedbackBatch",
    "coerce_individual_feedback",
    "copy_feedback_with_result",
    "feedback_constraint_violation",
]
