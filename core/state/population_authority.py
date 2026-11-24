"""One owner for the in-memory population projection and publication cursor."""
from __future__ import annotations

from copy import copy
from dataclasses import dataclass, field, fields
from typing import Any, ClassVar

import numpy as np
from blackbase.types import CandidateBatch


@dataclass
class PopulationAuthority:
    """Mutable working projection of the fenced AuthorityStore edge.

    CandidateBatch, provenance, partition values and Snapshot handles are
    immutable protocol values. Arrays and containers are copied on capture.
    Evaluation events and consumed budgets deliberately live outside this
    rollback owner. Adding a state field automatically includes it in rollback.
    """
    name: ClassVar[str] = "solver.authority"
    population: np.ndarray | None = None
    objectives: np.ndarray | None = None
    violations: np.ndarray | None = None
    candidate_batch: CandidateBatch | None = None
    candidate_provenance: tuple = ()
    active_provenance: list = field(default_factory=list)
    partitions: dict = field(default_factory=dict)
    mode: str = "step_batch"
    snapshot_handle: Any = None
    snapshot_generation: int | None = None
    active_population_ref: Any = None
    snapshot_transaction: dict | None = None

    def snapshot_step_state(self) -> dict[str, Any]:
        return {item.name: copy(getattr(self, item.name)) for item in fields(self)}

    def restore_step_state(self, state: dict[str, Any]) -> None:
        expected = {item.name for item in fields(self)}
        if set(state) != expected:
            raise ValueError("population authority snapshot fields disagree with its schema")
        for name, value in state.items():
            setattr(self, name, copy(value))
        # A copied array has a different object identity; consumers rebind its
        # provenance through the authoritative CandidateBatch/token projection.
        self.active_population_ref = None

    def commit_step_state(self, state):
        return None

    def step_transaction_children(self):
        return ()


class IncumbentParticipant:
    """Adapt the existing atomic incumbent owner to the shared transaction."""
    name = "solver.incumbent"

    def __init__(self, solver):
        self.solver = solver

    def snapshot_step_state(self):
        return self.solver._capture_incumbent_transaction_state()

    def restore_step_state(self, state):
        self.solver._restore_incumbent_transaction_state(state)

    def commit_step_state(self, state):
        return None

    def step_transaction_children(self):
        return ()
