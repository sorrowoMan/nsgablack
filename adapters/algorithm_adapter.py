"""
Algorithm adapter interface for composable solvers.

Adapters provide candidate proposals and consume evaluation feedback.
Inherits the unified AdapterBase from blackbase and adds nsgablack-specific
enhancements (numpy RNG, strict snapshot validation, extended contract).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

import numpy as np
from blackbase.wire import freeze_wire_mapping, thaw_wire_mapping

from blackbase.abc import AdapterBase
from blackbase.contracts import BatchDisposition
from blackbase.context import RuntimeContextProjection

from .runtime_projection import aggregate_adapter_runtime_projections


@dataclass(frozen=True)
class PopulationPartition:
    """One stable Adapter-owned evaluated-population partition.

    A composite Adapter must not concatenate unrelated child populations merely
    to satisfy the legacy single-population surface.  Instead it publishes one
    partition per stable child/role/unit identity.  Candidate tokens remain
    aligned with the numeric rows so the Solver can retain semantic identity.
    """

    partition_id: str
    population: np.ndarray
    objectives: np.ndarray
    violations: np.ndarray
    candidate_tokens: Sequence[str | None] = field(default_factory=tuple)
    owner: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        partition_id = str(self.partition_id or "").strip()
        if not partition_id:
            raise ValueError("PopulationPartition.partition_id must not be empty")
        pop, obj, vio = AlgorithmAdapter.validate_population_snapshot(
            self.population,
            self.objectives,
            self.violations,
        )
        tokens = tuple(self.candidate_tokens)
        if not tokens:
            tokens = (None,) * int(pop.shape[0])
        if len(tokens) != int(pop.shape[0]):
            raise ValueError(
                "PopulationPartition candidate tokens must align with population rows"
            )
        normalized_tokens = tuple(
            None if token is None else str(token).strip() or None
            for token in tokens
        )
        pop = np.asarray(pop, dtype=float).copy()
        obj = np.asarray(obj, dtype=float).copy()
        vio = np.asarray(vio, dtype=float).reshape(-1).copy()
        pop.setflags(write=False)
        obj.setflags(write=False)
        vio.setflags(write=False)
        object.__setattr__(self, "partition_id", partition_id)
        object.__setattr__(self, "population", pop)
        object.__setattr__(self, "objectives", obj)
        object.__setattr__(self, "violations", vio)
        object.__setattr__(self, "candidate_tokens", normalized_tokens)
        object.__setattr__(self, "owner", str(self.owner or ""))
        object.__setattr__(
            self,
            "metadata",
            freeze_wire_mapping(
                self.metadata,
                path="population_partition.metadata",
            ),
        )

    def with_prefix(self, prefix: str) -> "PopulationPartition":
        normalized = str(prefix or "").strip().strip("/")
        if not normalized:
            return self
        return PopulationPartition(
            partition_id=f"{normalized}/{self.partition_id}",
            population=self.population,
            objectives=self.objectives,
            violations=self.violations,
            candidate_tokens=self.candidate_tokens,
            owner=self.owner,
            metadata=self.metadata,
        )

    def without_prefix(self, prefix: str) -> "PopulationPartition":
        normalized = str(prefix or "").strip().strip("/")
        marker = f"{normalized}/"
        if not normalized or not self.partition_id.startswith(marker):
            raise ValueError(
                f"population partition {self.partition_id!r} is outside prefix {normalized!r}"
            )
        return PopulationPartition(
            partition_id=self.partition_id[len(marker):],
            population=self.population,
            objectives=self.objectives,
            violations=self.violations,
            candidate_tokens=self.candidate_tokens,
            owner=self.owner,
            metadata=self.metadata,
        )

    def as_dict(self) -> Dict[str, Any]:
        return {
            "schema": "nsgablack.population_partition/v1",
            "partition_id": self.partition_id,
            "population": self.population.tolist(),
            "objectives": self.objectives.tolist(),
            "violations": self.violations.tolist(),
            "candidate_tokens": list(self.candidate_tokens),
            "owner": self.owner,
            "metadata": thaw_wire_mapping(self.metadata),
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "PopulationPartition":
        data = dict(payload or {})
        schema = str(data.get("schema", "nsgablack.population_partition/v1"))
        if schema != "nsgablack.population_partition/v1":
            raise ValueError(f"unsupported population partition schema: {schema}")
        return cls(
            partition_id=str(data.get("partition_id", "")),
            population=np.asarray(data.get("population", ()), dtype=float),
            objectives=np.asarray(data.get("objectives", ()), dtype=float),
            violations=np.asarray(data.get("violations", ()), dtype=float),
            candidate_tokens=tuple(data.get("candidate_tokens", ()) or ()),
            owner=str(data.get("owner", "")),
            metadata=dict(data.get("metadata", {}) or {}),
        )


def prefixed_population_partitions(
    prefix: str,
    adapter: Any,
) -> tuple[PopulationPartition, ...]:
    getter = getattr(adapter, "get_population_partitions", None)
    if not callable(getter):
        return ()
    return tuple(partition.with_prefix(prefix) for partition in tuple(getter() or ()))


def restore_prefixed_population_partitions(
    prefix: str,
    adapter: Any,
    partitions: Sequence[PopulationPartition],
) -> bool:
    normalized = str(prefix or "").strip().strip("/")
    marker = f"{normalized}/"
    selected = tuple(
        partition.without_prefix(normalized)
        for partition in tuple(partitions or ())
        if partition.partition_id.startswith(marker)
    )
    if not selected:
        return False
    setter = getattr(adapter, "set_population_partitions", None)
    if not callable(setter):
        raise TypeError(
            f"Adapter {type(adapter).__name__} cannot restore population partitions"
        )
    return bool(setter(selected))


def subset_adapter_feedback(feedback: Any, selector: Any) -> Any:
    """Slice rich feedback when available, preserving legacy tuple support."""

    subset = getattr(feedback, "subset", None)
    if callable(subset):
        return subset(selector)
    objectives, violations = feedback
    return np.asarray(objectives)[selector], np.asarray(violations)[selector]


class AlgorithmAdapter(AdapterBase):
    """Base adapter for integrating arbitrary optimization logic.

    Inherits AdapterBase and adds nsgablack-specific:
    - create_local_rng: numpy Generator (instead of stdlib Random)
    - validate_population_snapshot: strict numpy shape validation
    - coerce_candidates: numpy-aware candidate normalization
    - get_context_contract: extended with artifact_requires/provides, phase_in/out
    - resolve_config: adapter config normalization helper

    The Solver lifecycle supplies ``OptimizationFeedbackBatch`` to update().
    It remains pair-unpack compatible for legacy adapters; semantic adapters
    may inspect ``feedback.items`` for gradients, losses, metrics, or signals.
    """

    # Extended context contract (nsgablack-specific)
    artifact_requires = ()
    artifact_provides = ()
    phase_in = ()
    phase_out = ()
    state_recovery_level = "L0"
    state_recovery_notes = "No adapter-owned runtime state is guaranteed to roundtrip."
    population_state_mode = "none"

    def __init__(self, name: str, priority: int = 0) -> None:
        self.name = name
        self.priority = priority

    @staticmethod
    def resolve_config(
        *,
        config: Any,
        config_cls: Any,
        config_kwargs: Optional[Dict[str, Any]] = None,
        adapter_name: str = "adapter",
    ) -> Any:
        """Normalize adapter config from explicit config or inline kwargs."""
        kwargs = dict(config_kwargs or {})
        if config is not None and kwargs:
            raise ValueError(
                f"{adapter_name}: pass either config=... or inline config kwargs, not both."
            )
        if config is None:
            return config_cls(**kwargs) if kwargs else config_cls()
        if not isinstance(config, config_cls):
            raise TypeError(
                f"{adapter_name}: config must be {config_cls.__name__}, got {type(config).__name__}."
            )
        return config

    # --- Override: numpy-aware RNG ---

    def create_local_rng(self, solver: Any = None, seed: Optional[int] = None) -> np.random.Generator:
        """Create a component-local numpy RNG.

        Priority:
        1) explicit seed
        2) solver.fork_rng() if available
        3) independent default RNG
        """
        if seed is not None:
            return np.random.default_rng(int(seed))
        if solver is not None:
            fork = getattr(solver, "fork_rng", None)
            if callable(fork):
                try:
                    rng = fork(self.name)
                    if isinstance(rng, np.random.Generator):
                        return rng
                except Exception:
                    pass
        return np.random.default_rng()

    # --- Override: numpy-aware candidate normalization ---

    @staticmethod
    def coerce_candidates(value: Any) -> List[Any]:
        """Normalize propose() output without relying on ambiguous truthiness."""
        if value is None:
            return []
        if isinstance(value, np.ndarray):
            if value.ndim <= 1:
                return [value]
            return [np.asarray(row) for row in value]
        return list(value)

    # --- Override: strict numpy snapshot validation ---

    @staticmethod
    def validate_population_snapshot(
        population: np.ndarray,
        objectives: np.ndarray,
        violations: np.ndarray,
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Normalize and validate population snapshot payload.

        Contract:
        - population: (N, D) float
        - objectives: (N, M) float
        - violations: (N,) float
        """
        pop = np.asarray(population, dtype=float)
        obj = np.asarray(objectives, dtype=float)
        vio = np.asarray(violations, dtype=float).reshape(-1)

        if pop.ndim == 1:
            pop = pop.reshape(1, -1) if pop.size > 0 else pop.reshape(0, 0)
        if obj.ndim == 1:
            obj = obj.reshape(-1, 1) if obj.size > 0 else obj.reshape(0, 0)

        n = int(pop.shape[0]) if pop.ndim >= 2 else 0
        if obj.shape[0] != n or vio.shape[0] != n:
            raise ValueError(
                "Population snapshot shape mismatch: "
                f"population={tuple(pop.shape)}, objectives={tuple(obj.shape)}, violations={tuple(vio.shape)}"
            )
        return pop, obj, vio

    # --- Override: authoritative evaluated-population snapshot contract ---

    def get_population_snapshot(
        self,
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray] | None:
        """Return the Adapter-owned evaluated population, or ``None``.

        L1/single-trajectory Adapters must not expose their unevaluated successor
        state through this method.  They may provide component-specific current
        candidate accessors instead.
        """

        return None

    def set_population_snapshot(
        self,
        population: np.ndarray,
        objectives: np.ndarray,
        violations: np.ndarray,
    ) -> bool:
        """Optional authoritative population write-back for L2 Adapters."""
        _ = self.validate_population_snapshot(population, objectives, violations)
        return False

    def get_population_candidate_tokens(self) -> tuple[str | None, ...] | None:
        """Return tokens aligned with ``get_population_snapshot()``.

        Returning ``None`` means that the Adapter does not expose a population
        lineage surface.  A Solver may only infer tokens when the authoritative
        rows exactly equal one complete input batch; mixed/reordered semantic
        populations must implement this contract explicitly.
        """

        return None

    def set_population_candidate_tokens(
        self,
        candidate_tokens: Sequence[str | None],
    ) -> bool:
        """Optional token write-back paired with ``set_population_snapshot()``."""

        del candidate_tokens
        return False

    def get_population_partitions(self) -> tuple[PopulationPartition, ...]:
        """Return the complete Adapter-owned population authority.

        A leaf/single-authority Adapter receives the default one-partition
        projection.  True composites override this method and keep child
        populations separate.
        """

        if str(getattr(self, "population_state_mode", "none")) == "none":
            return ()
        snapshot = self.get_population_snapshot()
        if snapshot is None:
            return ()
        population, objectives, violations = snapshot
        tokens = self.get_population_candidate_tokens()
        return (
            PopulationPartition(
                partition_id="population",
                population=population,
                objectives=objectives,
                violations=violations,
                candidate_tokens=() if tokens is None else tokens,
                owner=self.name,
            ),
        )

    def set_population_partitions(
        self,
        partitions: Sequence[PopulationPartition],
    ) -> bool:
        """Restore the population authority exported by this Adapter."""

        values = tuple(partitions or ())
        if len(values) != 1:
            if not values:
                return False
            raise ValueError(
                f"single-population Adapter {self.name!r} expected one partition"
            )
        partition = values[0]
        handled = self.set_population_snapshot(
            partition.population,
            partition.objectives,
            partition.violations,
        )
        if handled is False:
            return False
        token_handled = self.set_population_candidate_tokens(
            partition.candidate_tokens
        )
        if partition.candidate_tokens and token_handled is False:
            raise ValueError(
                f"Adapter {self.name!r} restored population values but rejected tokens"
            )
        return True

    @staticmethod
    def candidate_tokens_for(
        control: Any,
        candidates: Sequence[Any],
    ) -> tuple[str | None, ...]:
        resolver = getattr(control, "candidate_provenance_for", None)
        if not callable(resolver):
            return (None,) * len(candidates)
        tokens: list[str | None] = []
        for index, candidate in enumerate(candidates):
            provenance = resolver(candidate)
            if provenance is None:
                provenance = resolver(candidate, candidate_index=index)
            tokens.append(
                None
                if provenance is None
                else str(provenance.candidate_token)
            )
        return tuple(tokens)

    # --- Override: extended context contract ---

    def get_context_contract(self) -> Dict[str, Any]:
        requires = list(getattr(self, "context_requires", ()) or ())
        provides = list(getattr(self, "context_provides", ()) or ())
        mutates = list(getattr(self, "context_mutates", ()) or ())
        cache = list(getattr(self, "context_cache", ()) or ())
        artifact_requires = list(getattr(self, "artifact_requires", ()) or ())
        artifact_provides = list(getattr(self, "artifact_provides", ()) or ())
        phase_in = list(getattr(self, "phase_in", ()) or ())
        phase_out = list(getattr(self, "phase_out", ()) or ())
        feedback_requires = list(getattr(self, "feedback_requires", ()) or ())
        method_ids = list(getattr(self, "method_ids", ()) or ())

        notes_parts: List[str] = []
        for attr in ("context_notes", "recommended_mutators", "recommended_plugins", "companions", "recommended_suite"):
            value = getattr(self, attr, None)
            if value is None:
                continue
            if isinstance(value, str):
                text = value.strip()
                if text:
                    notes_parts.append(text)
                continue
            if isinstance(value, Iterable):
                items = [str(x).strip() for x in value if str(x).strip()]
                if items:
                    notes_parts.append(f"{attr}=" + ", ".join(items))
                continue
            text = str(value).strip()
            if text:
                notes_parts.append(f"{attr}={text}")

        return {
            "requires": requires,
            "provides": provides,
            "mutates": mutates,
            "cache": cache,
            "artifact_requires": artifact_requires,
            "artifact_provides": artifact_provides,
            "phase_in": phase_in,
            "phase_out": phase_out,
            "feedback_requires": feedback_requires,
            "method_ids": method_ids,
            "notes": " | ".join(notes_parts) if notes_parts else None,
        }

class CompositeAdapter(AlgorithmAdapter):
    """Combine multiple adapters and merge their proposals."""
    context_requires = ()
    context_provides = ()
    context_mutates = ()
    context_cache = ()
    context_notes = "Composite adapter: unions child adapter contracts."
    state_recovery_level = "L2"
    state_recovery_notes = "Restores stable child population partitions, tokens, and child adapter states."
    population_state_mode = "partitioned"

    def __init__(self, adapters: Sequence[AlgorithmAdapter], name: str = "composite", priority: int = 0) -> None:
        super().__init__(name=name, priority=priority)
        self.adapters = list(adapters)
        self._last_ranges: List[Tuple[AlgorithmAdapter, int, int]] = []
        self._last_projection_writers: Dict[str, str] = {}

    def setup(self, control: Any) -> None:
        self._last_projection_writers = {}
        for adapter in self.adapters:
            adapter.setup(control)

    def propose(self, control: Any, context: Dict[str, Any]) -> Sequence[Any]:
        candidates: List[np.ndarray] = []
        self._last_ranges = []
        for adapter in self.adapters:
            start = len(candidates)
            proposed = self.coerce_candidates(adapter.propose(control, context))
            candidates.extend(proposed)
            end = len(candidates)
            self._last_ranges.append((adapter, start, end))
        return candidates

    def update(
        self,
        control: Any,
        candidates: Sequence[Any],
        feedback: Any,
        context: Dict[str, Any],
    ) -> None:
        objectives, violations = feedback
        if not self._last_ranges:
            if len(candidates) == 0:
                return
            raise RuntimeError("CompositeAdapter.update requires a preceding propose call")
        expected_count = sum(end - start for _adapter, start, end in self._last_ranges)
        if len(candidates) != expected_count:
            raise ValueError(
                "composite feedback does not match child proposal ranges: "
                f"candidates={len(candidates)}, allocated={expected_count}"
            )
        if len(objectives) != expected_count or len(violations) != expected_count:
            raise ValueError("composite candidate, objective, and violation counts must match")
        for adapter, start, end in self._last_ranges:
            if start == end:
                continue
            adapter.update(
                control,
                candidates[start:end],
                subset_adapter_feedback(feedback, slice(start, end)),
                context,
            )

    def on_proposal_disposition(
        self,
        control: Any,
        disposition: BatchDisposition,
        context: Dict[str, Any],
    ) -> None:
        reconciled: List[Tuple[AlgorithmAdapter, int, int]] = []
        cursor = 0
        for adapter, start, end in self._last_ranges:
            child_disposition = disposition.for_range(start, end)
            adapter.on_proposal_disposition(
                control,
                child_disposition,
                context,
            )
            if child_disposition.accepted_count > 0:
                next_cursor = cursor + child_disposition.accepted_count
                reconciled.append((adapter, cursor, next_cursor))
                cursor = next_cursor
        self._last_ranges = reconciled

    def teardown(self, control: Any) -> None:
        for adapter in self.adapters:
            adapter.teardown(control)

    def _child_prefix(self, index: int, adapter: AlgorithmAdapter) -> str:
        return f"child:{int(index)}:{adapter.name}"

    def get_population_partitions(self) -> tuple[PopulationPartition, ...]:
        out: list[PopulationPartition] = []
        for index, adapter in enumerate(self.adapters):
            out.extend(
                prefixed_population_partitions(
                    self._child_prefix(index, adapter),
                    adapter,
                )
            )
        return tuple(out)

    def set_population_partitions(
        self,
        partitions: Sequence[PopulationPartition],
    ) -> bool:
        values = tuple(partitions or ())
        handled = False
        for index, adapter in enumerate(self.adapters):
            handled = (
                restore_prefixed_population_partitions(
                    self._child_prefix(index, adapter),
                    adapter,
                    values,
                )
                or handled
            )
        unknown = {
            partition.partition_id
            for partition in values
            if not any(
                partition.partition_id.startswith(
                    self._child_prefix(index, adapter) + "/"
                )
                for index, adapter in enumerate(self.adapters)
            )
        }
        if unknown:
            raise ValueError(
                "CompositeAdapter checkpoint contains unknown population partitions: "
                + ", ".join(sorted(unknown))
            )
        return handled or not values

    def get_state(self) -> Dict[str, Any]:
        return {
            "schema": "nsgablack.composite_adapter_state/v2",
            "children": [
                {
                    "index": int(index),
                    "name": adapter.name,
                    "class": f"{type(adapter).__module__}.{type(adapter).__qualname__}",
                    "state": adapter.get_state(),
                }
                for index, adapter in enumerate(self.adapters)
            ],
            "population_partitions": [
                partition.as_dict()
                for partition in self.get_population_partitions()
            ],
        }

    def set_state(self, state: Dict[str, Any]) -> None:
        if not state:
            return
        children = tuple(state.get("children", ()) or ())
        if children:
            if len(children) != len(self.adapters):
                raise ValueError("CompositeAdapter child state count mismatch")
            for index, (adapter, child) in enumerate(zip(self.adapters, children)):
                if int(child.get("index", index)) != index:
                    raise ValueError("CompositeAdapter child state order mismatch")
                if str(child.get("name", adapter.name)) != adapter.name:
                    raise ValueError("CompositeAdapter child state identity mismatch")
                adapter.set_state(dict(child.get("state", {}) or {}))
        raw_partitions = tuple(state.get("population_partitions", ()) or ())
        if raw_partitions:
            self.set_population_partitions(
                tuple(PopulationPartition.from_dict(item) for item in raw_partitions)
            )

    def get_context_contract(self) -> Dict[str, Any]:
        contract = super().get_context_contract()
        requires = list(contract.get("requires", ()) or ())
        provides = list(contract.get("provides", ()) or ())
        mutates = list(contract.get("mutates", ()) or ())
        cache = list(contract.get("cache", ()) or ())
        for adapter in self.adapters:
            sub = adapter.get_context_contract()
            requires.extend(list(sub.get("requires", ()) or ()))
            provides.extend(list(sub.get("provides", ()) or ()))
            mutates.extend(list(sub.get("mutates", ()) or ()))
            cache.extend(list(sub.get("cache", ()) or ()))
        return {
            "requires": requires,
            "provides": provides,
            "mutates": mutates,
            "cache": cache,
            "notes": "composite",
        }

    def get_runtime_context_projection(self, solver: Any) -> RuntimeContextProjection:
        aggregation = aggregate_adapter_runtime_projections(
            solver,
            owner_source=f"adapter.{self.__class__.__name__}",
            children=tuple(
                (
                    f"adapter.child.{index}:{adapter.__class__.__name__}",
                    adapter,
                )
                for index, adapter in enumerate(self.adapters)
            ),
        )
        self._last_projection_writers = dict(aggregation.field_sources)
        return aggregation.projection

    def get_runtime_context_projection_sources(self, solver: Any) -> Dict[str, str]:
        del solver
        return dict(self._last_projection_writers)
