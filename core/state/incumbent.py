"""Atomic run-wide incumbent state for optimization solvers."""

from __future__ import annotations

from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, Mapping

import numpy as np


DEFAULT_INCUMBENT_POLICY_ID = "objective_sum/v1"


def _freeze_payload(value: Any, *, path: str) -> Any:
    """Recursively copy a JSON-like value into immutable containers."""

    if isinstance(value, np.generic):
        return _freeze_payload(value.item(), path=path)
    if isinstance(value, np.ndarray):
        return tuple(
            _freeze_payload(item, path=f"{path}[]")
            for item in value.tolist()
        )
    if isinstance(value, Mapping):
        frozen = {
            str(key): _freeze_payload(item, path=f"{path}.{key}")
            for key, item in value.items()
        }
        return MappingProxyType(frozen)
    if isinstance(value, (list, tuple)):
        return tuple(
            _freeze_payload(item, path=f"{path}[]")
            for item in value
        )
    if isinstance(value, (set, frozenset)):
        frozen_items = [_freeze_payload(item, path=f"{path}[]") for item in value]
        return tuple(sorted(frozen_items, key=repr))
    if value is None or isinstance(value, (str, bytes, bool, int, float)):
        return value
    raise TypeError(
        f"{path} contains unsupported mutable value type {type(value).__name__}"
    )


def _thaw_payload(value: Any) -> Any:
    """Return a detached transport-safe copy of an immutable payload."""

    if isinstance(value, Mapping):
        return {str(key): _thaw_payload(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_thaw_payload(item) for item in value]
    if isinstance(value, np.ndarray):
        return value.tolist()
    return value


def _immutable_float_vector(value: Any) -> np.ndarray:
    copied = np.asarray(value, dtype=float).reshape(-1).copy()
    return np.frombuffer(copied.tobytes(order="C"), dtype=copied.dtype).reshape(
        copied.shape
    )


class ScalarizationError(RuntimeError):
    """Raised when the configured incumbent scalarizer cannot score a candidate."""

    def __init__(
        self,
        message: str,
        *,
        candidate_index: int | None = None,
        objective_row: Any = None,
        violation: float | None = None,
        phase: str = "incumbent_selection",
        policy_id: str | None = None,
    ) -> None:
        super().__init__(str(message))
        self.candidate_index = candidate_index
        self.objective_row = (
            None
            if objective_row is None
            else np.asarray(objective_row, dtype=float).reshape(-1).copy()
        )
        self.violation = None if violation is None else float(violation)
        self.phase = str(phase)
        self.policy_id = None if policy_id is None else str(policy_id)


@dataclass(frozen=True)
class CandidateProvenance:
    """Stable identity and lineage carried beside a candidate batch row."""

    candidate_token: str
    source_kind: str = "evaluation"
    source_run_id: str | None = None
    warm_start_id: str | None = None
    proposal_id: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        token = str(self.candidate_token or "").strip()
        if not token:
            raise ValueError("CandidateProvenance.candidate_token must not be empty")
        source_kind = str(self.source_kind or "evaluation").strip().lower()
        object.__setattr__(self, "candidate_token", token)
        object.__setattr__(self, "source_kind", source_kind)
        object.__setattr__(
            self,
            "source_run_id",
            None if self.source_run_id is None else str(self.source_run_id),
        )
        object.__setattr__(
            self,
            "warm_start_id",
            None if self.warm_start_id is None else str(self.warm_start_id),
        )
        object.__setattr__(
            self,
            "proposal_id",
            None if self.proposal_id is None else str(self.proposal_id),
        )
        object.__setattr__(
            self,
            "metadata",
            _freeze_payload(dict(self.metadata or {}), path="CandidateProvenance.metadata"),
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "candidate_token": self.candidate_token,
            "source_kind": self.source_kind,
            "source_run_id": self.source_run_id,
            "warm_start_id": self.warm_start_id,
            "proposal_id": self.proposal_id,
            "metadata": _thaw_payload(self.metadata),
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "CandidateProvenance":
        data = dict(payload or {})
        return cls(
            candidate_token=str(data.get("candidate_token", "")),
            source_kind=str(data.get("source_kind", "evaluation")),
            source_run_id=data.get("source_run_id"),
            warm_start_id=data.get("warm_start_id"),
            proposal_id=data.get("proposal_id"),
            metadata=dict(data.get("metadata", {}) or {}),
        )


@dataclass(frozen=True)
class IncumbentState:
    """One evaluated candidate and every fact used to make it authoritative.

    The numpy payloads are defensively copied and marked read-only.  Replacing
    an incumbent therefore happens by replacing this complete object, never by
    mutating candidate/objective/violation fields independently.
    """

    candidate: np.ndarray
    objectives: np.ndarray
    constraint_violation: float
    score: float
    policy_id: str = DEFAULT_INCUMBENT_POLICY_ID
    policy_context: Mapping[str, Any] = field(default_factory=dict)
    evaluation_id: str | None = None
    candidate_token: str | None = None
    source: str = "evaluation"
    source_run_id: str | None = None
    warm_start_id: str | None = None
    proposal_id: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        candidate = _immutable_float_vector(self.candidate)
        objectives = _immutable_float_vector(self.objectives)
        if candidate.size == 0:
            raise ValueError("IncumbentState.candidate must not be empty")
        if objectives.size == 0:
            raise ValueError("IncumbentState.objectives must not be empty")
        violation = float(self.constraint_violation)
        score = float(self.score)
        if not np.isfinite(violation):
            raise ValueError("IncumbentState.constraint_violation must be finite")
        if not np.isfinite(score):
            raise ValueError("IncumbentState.score must be finite")
        policy_id = str(self.policy_id or "").strip()
        if not policy_id:
            raise ValueError("IncumbentState.policy_id must not be empty")
        source = str(self.source or "evaluation").strip().lower()
        object.__setattr__(self, "candidate", candidate)
        object.__setattr__(self, "objectives", objectives)
        object.__setattr__(self, "constraint_violation", violation)
        object.__setattr__(self, "score", score)
        object.__setattr__(self, "policy_id", policy_id)
        object.__setattr__(
            self,
            "policy_context",
            _freeze_payload(
                dict(self.policy_context or {}),
                path="IncumbentState.policy_context",
            ),
        )
        object.__setattr__(self, "evaluation_id", None if self.evaluation_id is None else str(self.evaluation_id))
        object.__setattr__(
            self,
            "candidate_token",
            None if self.candidate_token is None else str(self.candidate_token),
        )
        object.__setattr__(self, "source", source)
        object.__setattr__(self, "source_run_id", None if self.source_run_id is None else str(self.source_run_id))
        object.__setattr__(
            self,
            "warm_start_id",
            None if self.warm_start_id is None else str(self.warm_start_id),
        )
        object.__setattr__(
            self,
            "proposal_id",
            None if self.proposal_id is None else str(self.proposal_id),
        )
        object.__setattr__(
            self,
            "metadata",
            _freeze_payload(dict(self.metadata or {}), path="IncumbentState.metadata"),
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "candidate": self.candidate.tolist(),
            "objectives": self.objectives.tolist(),
            "constraint_violation": self.constraint_violation,
            "score": self.score,
            "policy_id": self.policy_id,
            "policy_context": _thaw_payload(self.policy_context),
            "evaluation_id": self.evaluation_id,
            "candidate_token": self.candidate_token,
            "source": self.source,
            "source_run_id": self.source_run_id,
            "warm_start_id": self.warm_start_id,
            "proposal_id": self.proposal_id,
            "metadata": _thaw_payload(self.metadata),
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "IncumbentState":
        data = dict(payload or {})
        return cls(
            candidate=data.get("candidate"),
            objectives=data.get("objectives"),
            constraint_violation=data.get("constraint_violation"),
            score=data.get("score"),
            policy_id=data.get("policy_id", DEFAULT_INCUMBENT_POLICY_ID),
            policy_context=dict(data.get("policy_context", {}) or {}),
            evaluation_id=data.get("evaluation_id"),
            candidate_token=data.get("candidate_token"),
            source=data.get("source", "evaluation"),
            source_run_id=data.get("source_run_id"),
            warm_start_id=data.get("warm_start_id"),
            proposal_id=data.get("proposal_id"),
            metadata=dict(data.get("metadata", {}) or {}),
        )


__all__ = [
    "DEFAULT_INCUMBENT_POLICY_ID",
    "CandidateProvenance",
    "IncumbentState",
    "ScalarizationError",
]
