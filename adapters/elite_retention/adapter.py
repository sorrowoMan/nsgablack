"""Elite-derived proposal injection inside the canonical step transaction."""

from __future__ import annotations

import copy
from dataclasses import dataclass
from typing import Any, Dict, Mapping, Sequence

import numpy as np
from blackbase.contracts import BatchDisposition
from blackbase.types import UnknownState

from ..unit_backed import UnitBackedAdapter, UnitField
from ...representation.structure_builders import ArchiveUnitBuilder
from ..algorithm_adapter import AlgorithmAdapter, PopulationPartition
from ..empty_outcome import child_empty_proposal_outcome
from ...core.state.solution_pool import SolutionRef
from ...context_keys import KEY_SOLUTION_INPUT_REF


@dataclass(frozen=True)
class EliteRetentionConfig:
    retention_probability: float = 0.9
    retention_ratio: float = 0.1
    history_size: int = 1
    mutation_scale: float = 0.01

    def __post_init__(self) -> None:
        if not 0.0 <= float(self.retention_probability) <= 1.0:
            raise ValueError("retention_probability must be within [0, 1]")
        if not 0.0 <= float(self.retention_ratio) <= 1.0:
            raise ValueError("retention_ratio must be within [0, 1]")
        if int(self.history_size) <= 0:
            raise ValueError("history_size must be positive")
        if float(self.mutation_scale) < 0.0:
            raise ValueError("mutation_scale must be non-negative")


class EliteRetentionAdapter(UnitBackedAdapter):
    """Wrap an Adapter and inject elite-derived candidates before evaluation.

    The former Plugin implementation evaluated and published replacement rows
    after a generation had already committed.  This wrapper keeps the same
    search intention while ensuring every derived candidate receives the
    ordinary CandidateBatch token, EvaluationEvent, acceptance decision and
    authority Snapshot transaction.
    """
    unit_builder_type = ArchiveUnitBuilder
    unit_schema = ArchiveUnitBuilder.unit_type.schema
    _archive = UnitField("entries")


    population_state_mode = "delegate"
    state_recovery_level = "L2"
    state_recovery_notes = (
        "Delegates population authority and checkpoints a bounded elite archive."
    )
    context_requires = ()
    context_provides = ()
    context_mutates = ()
    context_cache = ()
    context_notes = "Delegates context to the inner Adapter; elite archive and RNG remain in explicit Unit/checkpoint state."

    def validate_local_unit_contract(self):
        self._validate_injection()

    def _validate_injection(self):
        if (self.config.retention_probability > 0 and self.config.retention_ratio > 0
                and not self.inner.can_replace_proposals()):
            raise ValueError(f"EliteRetention cannot replace structurally bound proposals from {self.inner.name}")

    def __init__(
        self,
        inner: AlgorithmAdapter,
        config: EliteRetentionConfig | None = None,
        *,
        name: str = "elite_retention",
        priority: int = 0,
        unit_binding=None,
    ) -> None:
        if not isinstance(inner, AlgorithmAdapter):
            raise TypeError("EliteRetentionAdapter.inner must be an AlgorithmAdapter")
        super().__init__(name=name, priority=priority, unit_binding=unit_binding)
        self.inner = inner
        self.config = config or EliteRetentionConfig()
        self._archive: list[dict[str, Any]] = []
        self._rng = np.random.default_rng()

    def setup(self, control: Any) -> None:
        self._setup_local_state(control)
        self.inner.setup(control)

    def _setup_local_state(self, control: Any) -> None:
        """Initialize wrapper-owned state without reinitializing the inner Adapter."""
        self._validate_injection()
        self._archive = []
        self._rng = self.create_local_rng(solver=control)

    def teardown(self, control: Any) -> None:
        self.inner.teardown(control)

    @property
    def get_pool_refinement_results(self):
        # Refinement selection belongs to the inner algorithm, not this archive's
        # independent retention score.
        return getattr(self.inner, "get_pool_refinement_results", None)

    def pool_result_owner(self):
        return self.inner.pool_result_owner()

    def get_solution_pool_roots(self, control):
        refs = []
        for item in self._archive:
            value = item.get("solution_ref")
            if value is None:
                # Legacy direct updates remain usable, but cannot authorize GC
                # by guessing an exact version from equal candidate values.
                return None
            refs.append(SolutionRef.from_dict(dict(value)))
        return tuple(refs)

    def propose(self, control: Any, context: Dict[str, Any]) -> Sequence[Any]:
        self._validate_injection()
        input_ref = context.get(KEY_SOLUTION_INPUT_REF)
        intake = input_ref is not None and control.solution_pool.input_remaining(input_ref) > 0
        proposed = self.coerce_candidates(self.inner.propose(control, context))
        if (
            not proposed
            or intake
            or self.config.retention_ratio <= 0
            or not self._archive
            or self._rng.random() >= float(self.config.retention_probability)
        ):
            return proposed
        count = min(
            len(proposed),
            max(1, int(np.ceil(len(proposed) * float(self.config.retention_ratio)))),
        )
        selected = self._rng.choice(len(self._archive), size=count, replace=True)
        for offset, archive_index in enumerate(np.asarray(selected).reshape(-1)):
            entry = self._archive[int(archive_index)]
            value = entry.get("solution_ref")
            if value is None:
                base = copy.deepcopy(entry["candidate"])
            else:
                # Read through the control surface so the new proposal retains
                # its archived parent's token/version in provenance.
                batch = control.read_solutions((SolutionRef.from_dict(dict(value)),))
                state = batch.semantic_states[0]
                base = state if isinstance(entry["candidate"], UnknownState) else batch.numeric_matrix[0]
                provenance = control.candidate_provenance_for(state)
                control.bind_candidate_provenance((base,), (provenance,), activate=False)
            mutate = getattr(control, "mutate_candidate", None)
            if callable(mutate):
                derived = self.inner.mutate_candidate(control, base, context)
            else:
                arr = np.asarray(base, dtype=float)
                derived = arr + self._rng.normal(
                    0.0,
                    float(self.config.mutation_scale),
                    size=arr.shape,
                )
            proposed[len(proposed) - count + offset] = derived
        return proposed

    def on_proposal_repair(self, control, repair, context):
        self._forward_proposal_repair(control, repair, context)

    def proposal_repair_children(self, repair, context):
        return ((self.inner, repair, context),)

    def _proposal_contexts(self, proposed_count, context):
        return self.inner.get_proposal_contexts(proposed_count, context)

    def on_proposal_disposition(
        self,
        control: Any,
        disposition: BatchDisposition,
        context: Dict[str, Any],
    ) -> None:
        self.inner.on_proposal_disposition(control, disposition, context)

    def update(
        self,
        control: Any,
        candidates: Sequence[Any],
        feedback: Any,
        context: Dict[str, Any],
    ) -> None:
        self.inner.update(control, candidates, feedback, context)
        objectives, violations = feedback
        obj = np.asarray(objectives, dtype=float)
        if obj.ndim == 1:
            obj = obj.reshape(-1, 1)
        vio = np.asarray(violations, dtype=float).reshape(-1)
        if len(candidates) != obj.shape[0] or obj.shape[0] != vio.shape[0]:
            raise ValueError("elite archive update is cardinality-inconsistent")
        for index, candidate in enumerate(candidates):
            objective = np.asarray(obj[index], dtype=float).reshape(-1).copy()
            violation = float(vio[index])
            score = float(np.sum(objective))
            items = getattr(feedback, "items", ())
            value = items[index].info.get("accepted_solution_ref") if items else None
            ref = None if value is None else SolutionRef.from_dict(dict(value))
            self._archive.append(
                {
                    "candidate": copy.deepcopy(candidate),
                    "objectives": objective,
                    "violation": violation,
                    "score": score,
                    "solution_ref": None if ref is None else ref.as_dict(),
                }
            )
        self._archive.sort(
            key=lambda item: (
                1 if float(item["violation"]) > 0.0 else 0,
                max(0.0, float(item["violation"])),
                float(item["score"]),
            )
        )
        del self._archive[int(self.config.history_size) :]

    def get_empty_proposal_outcome(
        self,
        control: Any,
        context: Mapping[str, Any],
    ) -> Any | None:
        return child_empty_proposal_outcome(self.inner, control, context)

    def _get_algorithm_state(self) -> Dict[str, Any]:
        return {
            "schema": "nsgablack.elite_retention_state/v1",
            "name": self.name,
            "config": {
                "retention_probability": self.config.retention_probability,
                "retention_ratio": self.config.retention_ratio,
                "history_size": self.config.history_size,
                "mutation_scale": self.config.mutation_scale,
            },
            "archive": copy.deepcopy(self._archive),
            "rng_state": copy.deepcopy(self._rng.bit_generator.state),
            "inner_name": self.inner.name,
            "inner": self.inner.get_state(),
        }

    def _set_algorithm_state(self, state: Dict[str, Any]) -> None:
        if str(state.get("schema", "")) != "nsgablack.elite_retention_state/v1":
            raise ValueError("unsupported EliteRetentionAdapter state schema")
        if str(state.get("name", self.name)) != self.name:
            raise ValueError("EliteRetentionAdapter checkpoint identity mismatch")
        if str(state.get("inner_name", self.inner.name)) != self.inner.name:
            raise ValueError("EliteRetentionAdapter inner identity mismatch")
        expected = {
            "retention_probability": self.config.retention_probability,
            "retention_ratio": self.config.retention_ratio,
            "history_size": self.config.history_size,
            "mutation_scale": self.config.mutation_scale,
        }
        if dict(state.get("config", {}) or {}) != expected:
            raise ValueError("EliteRetentionAdapter checkpoint configuration mismatch")
        self._archive = copy.deepcopy(list(state.get("archive", ()) or ()))
        rng_state = state.get("rng_state")
        if isinstance(rng_state, Mapping):
            self._rng.bit_generator.state = copy.deepcopy(dict(rng_state))
        inner_state = state.get("inner")
        if isinstance(inner_state, Mapping):
            self.inner.set_state(dict(inner_state))

    def step_transaction_children(self) -> Sequence[AlgorithmAdapter]:
        return (self.inner,)

    def _snapshot_algorithm_step_state(self) -> Mapping[str, Any]:
        return {
            "schema": "nsgablack.elite_retention_step/v1",
            "archive": copy.deepcopy(self._archive),
            "rng_state": copy.deepcopy(self._rng.bit_generator.state),
        }

    def _restore_algorithm_step_state(self, state: Mapping[str, Any]) -> None:
        if str(state.get("schema", "")) != "nsgablack.elite_retention_step/v1":
            raise ValueError("unsupported EliteRetentionAdapter step schema")
        self._archive = copy.deepcopy(list(state.get("archive", ()) or ()))
        rng_state = state.get("rng_state")
        if isinstance(rng_state, Mapping):
            self._rng.bit_generator.state = copy.deepcopy(dict(rng_state))

    def resolve_population_state_mode(self) -> str:
        return str(self.inner.resolve_population_state_mode())

    def supported_population_state_modes(self) -> frozenset[str]:
        return self.inner.supported_population_state_modes()

    def get_population_snapshot(self):
        return self.inner.get_population_snapshot()

    def set_population_snapshot(self, population, objectives, violations) -> bool:
        return bool(self.inner.set_population_snapshot(population, objectives, violations))

    def supports_population_state_delivery(self):
        return self.inner.supports_population_state_delivery()

    def set_population_state(self, control, batch, feedback, *, solution_refs, provenance):
        return self.inner.set_population_state(control, batch, feedback,
            solution_refs=solution_refs, provenance=provenance)

    def get_population_solution_refs(self, control):
        return self.inner.get_population_solution_refs(control)

    def get_population_candidate_tokens(self):
        return self.inner.get_population_candidate_tokens()

    def set_population_candidate_tokens(self, candidate_tokens) -> bool:
        return bool(self.inner.set_population_candidate_tokens(candidate_tokens))

    def get_population_partitions(self) -> tuple[PopulationPartition, ...]:
        getter = getattr(self.inner, "get_population_partitions", None)
        return tuple(getter() or ()) if callable(getter) else ()

    def set_population_partitions(
        self,
        partitions: Sequence[PopulationPartition],
    ) -> bool:
        setter = getattr(self.inner, "set_population_partitions", None)
        return bool(setter(partitions)) if callable(setter) else False

    def get_runtime_context_projection(self, solver: Any) -> Dict[str, Any]:
        projector = getattr(self.inner, "get_runtime_context_projection", None)
        return dict(projector(solver) or {}) if callable(projector) else {}

    def get_runtime_context_projection_sources(self, solver: Any) -> Dict[str, str]:
        getter = getattr(self.inner, "get_runtime_context_projection_sources", None)
        return dict(getter(solver) or {}) if callable(getter) else {}
