"""Scoped search tasks and candidate origins; independent of Project/L0 tasks."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping
from uuid import uuid4

import numpy as np
from blackbase.types import UnknownState

from nsgablack.context_keys import (
    KEY_PHASE, KEY_REGION_BOUNDS, KEY_REGION_ID, KEY_ROLE, KEY_ROLE_ADAPTER,
    KEY_ROLE_INDEX, KEY_SEEDS, KEY_STRATEGY, KEY_STRATEGY_ID, KEY_TASK,
)

STRATEGY_TASK_SCHEMA = "nsgablack.strategy_task/v1"
STRATEGY_ORIGIN_SCHEMA = "nsgablack.strategy_origin/v1"
STRATEGY_ORIGIN_METADATA = "nsgablack.strategy_origins"
TASK_CONTEXT_KEYS = (
    KEY_TASK, KEY_ROLE, KEY_ROLE_INDEX, KEY_ROLE_ADAPTER, KEY_STRATEGY,
    KEY_STRATEGY_ID, KEY_PHASE, KEY_REGION_ID, KEY_REGION_BOUNDS, KEY_SEEDS,
)


def _path(value: Any) -> tuple[str, ...]:
    if isinstance(value, (str, bytes)):
        raise TypeError("owner_path must contain path segments")
    result = tuple(value)
    if not result or any(not isinstance(p, str) or not p or "/" in p for p in result):
        raise ValueError("owner_path requires nonempty, slash-free segments")
    return result


@dataclass(frozen=True)
class StrategyTask:
    """One immutable proposal request. Admission never rewrites its budget.

    ``task_id`` identifies this invocation (including retries); ``owner_path``
    identifies the instance. Local context aliases are derived copies only.
    Numeric seeds/bounds are invocation-local, not durable context payloads.
    """

    owner_path: tuple[str, ...]
    role: str
    unit_id: int
    role_index: int
    adapter_name: str
    step: int
    phase: str
    phase_step: int
    budget: int
    region_id: int | None = None
    region_bounds: tuple[tuple[float, ...], ...] | None = None
    seeds: tuple[tuple[float, ...], ...] = ()
    task_id: str = field(default_factory=lambda: uuid4().hex)
    parent_task_id: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "owner_path", _path(self.owner_path))
        for name in ("unit_id", "role_index", "step", "phase_step", "budget"):
            if type(getattr(self, name)) is not int or getattr(self, name) < 0:
                raise ValueError(f"StrategyTask.{name} must be a nonnegative integer")
        for name in ("role", "adapter_name", "phase", "task_id"):
            if not isinstance(getattr(self, name), str) or not getattr(self, name).strip():
                raise ValueError(f"StrategyTask.{name} must be a nonempty string")
        if self.region_id is not None and (type(self.region_id) is not int or self.region_id < 0):
            raise ValueError("region_id must be a nonnegative integer or None")
        if self.parent_task_id is not None and (
            not isinstance(self.parent_task_id, str) or not self.parent_task_id
            or self.parent_task_id == self.task_id
        ):
            raise ValueError("invalid parent_task_id")
        for name in ("region_bounds", "seeds"):
            values = getattr(self, name)
            if values is not None:
                object.__setattr__(self, name, tuple(tuple(float(v) for v in row) for row in values))

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema": STRATEGY_TASK_SCHEMA,
            **{name: getattr(self, name) for name in self.__dataclass_fields__},
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "StrategyTask":
        if not isinstance(value, Mapping) or value.get("schema") != STRATEGY_TASK_SCHEMA:
            raise ValueError("unsupported strategy task schema")
        return cls(**{name: value[name] for name in cls.__dataclass_fields__})

    @classmethod
    def from_context(cls, context: Mapping[str, Any]) -> "StrategyTask":
        return cls.from_dict(context[KEY_TASK])

    def bind(self, context: Mapping[str, Any]) -> dict[str, Any]:
        """Overlay ALL task fields, including None, on current lifecycle data."""
        return {
            **context,
            KEY_TASK: self.as_dict(),
            KEY_ROLE: self.role, KEY_ROLE_INDEX: self.role_index,
            KEY_ROLE_ADAPTER: self.adapter_name,
            KEY_STRATEGY: self.role, KEY_STRATEGY_ID: self.unit_id,
            KEY_PHASE: self.phase, KEY_REGION_ID: self.region_id,
            KEY_REGION_BOUNDS: self.region_bounds, KEY_SEEDS: self.seeds,
        }

    def summary(self) -> dict[str, Any]:
        """Bounded task description for telemetry; arrays remain local."""
        result = self.as_dict()
        result["schema"] = "nsgablack.strategy_task_summary/v1"
        result.pop("seeds")
        result.pop("region_bounds")
        result["seed_count"] = len(self.seeds)
        return result


@dataclass(frozen=True)
class StrategyOrigin:
    """One routing frame attached to a candidate, before token allocation."""

    owner_path: tuple[str, ...]
    task_id: str
    role: str
    unit_id: int
    proposal_index: int
    phase: str
    step: int
    region_id: int | None
    parent_task_id: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "owner_path", _path(self.owner_path))
        for name in ("unit_id", "proposal_index", "step"):
            if type(getattr(self, name)) is not int or getattr(self, name) < 0:
                raise ValueError(f"StrategyOrigin.{name} must be a nonnegative integer")
        for name in ("task_id", "role", "phase"):
            if not isinstance(getattr(self, name), str) or not getattr(self, name):
                raise ValueError(f"StrategyOrigin.{name} must be nonempty")
        if self.region_id is not None and (type(self.region_id) is not int or self.region_id < 0):
            raise ValueError("origin region_id must be a nonnegative integer or None")

    def as_dict(self) -> dict[str, Any]:
        return {"schema": STRATEGY_ORIGIN_SCHEMA,
                **{name: getattr(self, name) for name in self.__dataclass_fields__}}

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "StrategyOrigin":
        if not isinstance(value, Mapping) or value.get("schema") != STRATEGY_ORIGIN_SCHEMA:
            raise ValueError("unsupported strategy origin schema")
        return cls(**{name: value[name] for name in cls.__dataclass_fields__})

    @classmethod
    def from_candidate(cls, candidate: UnknownState) -> tuple["StrategyOrigin", ...]:
        """Read the outer-to-inner route from a CandidateBatch semantic row."""
        result = tuple(cls.from_dict(row) for row in candidate.metadata.get(STRATEGY_ORIGIN_METADATA, ()))
        for parent, child in zip(result, result[1:]):
            if (child.parent_task_id != parent.task_id
                    or len(child.owner_path) <= len(parent.owner_path)
                    or child.owner_path[:len(parent.owner_path)] != parent.owner_path):
                raise ValueError("candidate origin route has inconsistent task ancestry")
        if len({item.task_id for item in result}) != len(result):
            raise ValueError("candidate origin route repeats a task")
        return result


def attach_strategy_origin(candidate: Any, task: StrategyTask, index: int, control: Any) -> UnknownState:
    """Preserve semantics and existing lineage; never allocate a second token."""
    lookup = getattr(control, "candidate_provenance_for", None)
    previous = lookup(candidate) if callable(lookup) else None
    if isinstance(candidate, UnknownState):
        state = candidate
    elif previous is not None:
        state = control.semantic_candidate_state(candidate)
    else:
        state = UnknownState(values=np.asarray(candidate))
    origin = StrategyOrigin(
        task.owner_path, task.task_id, task.role, task.unit_id, index,
        task.phase, task.step, task.region_id, task.parent_task_id,
    )
    descendants = StrategyOrigin.from_candidate(state)
    # A reused candidate's old route describes another proposal, not this one.
    if descendants and descendants[0].parent_task_id != task.task_id:
        descendants = ()
    if descendants and descendants[0].owner_path[:len(task.owner_path)] != task.owner_path:
        raise ValueError("nested candidate origin is outside its task owner path")
    result = state.with_meta(**{STRATEGY_ORIGIN_METADATA: [
        item.as_dict() for item in (origin, *descendants)
    ]})
    if previous is not None:
        control.bind_candidate_provenance([result], [previous], activate=False)
    return result


__all__ = ["StrategyTask", "StrategyOrigin"]
