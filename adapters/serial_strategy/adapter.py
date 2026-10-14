"""
Strategy chain adapter (macro-serial, micro-single).

Use cases:
- Simple sequential phases: NSGA2 -> VNS -> TR
- Serial groups: each phase can be a StrategyRouterAdapter
"""

from __future__ import annotations
from blackbase.plugin import report_soft_error as _report_optional_failure

from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Mapping, Optional, Sequence, Tuple, Union

import numpy as np
from blackbase.call_binding import CallCandidate, invoke_bound_once
from blackbase.contracts import BatchDisposition
from blackbase.context import RuntimeContextProjection

from ..algorithm_adapter import (
    AlgorithmAdapter,
    PopulationPartition,
    prefixed_population_partitions,
    restore_prefixed_population_partitions,
)
from ..runtime_projection import aggregate_adapter_runtime_projections
from ..empty_outcome import child_empty_proposal_outcome
from nsgablack.context_keys import KEY_PHASE, KEY_STRATEGY, KEY_STRATEGY_ID


PhaseAdapter = Union[AlgorithmAdapter, Callable[[], AlgorithmAdapter], Callable[[int], AlgorithmAdapter]]
AdvanceWhenFn = Callable[[Dict[str, Any]], bool]


@dataclass
class SerialPhaseSpec:
    name: str
    adapter: PhaseAdapter
    steps: int = -1  # -1 means "until end"
    advance_when: Optional[AdvanceWhenFn] = None
    enabled: bool = True


@dataclass
class SerialStrategyConfig:
    # List of (phase_name, steps) pairs; steps=-1 means "until end".
    phase_schedule: Tuple[Tuple[str, int], ...] = ()
    # If True, keep the last phase active after schedule end.
    repeat_last: bool = True


class StrategyChainAdapter(AlgorithmAdapter):
    """
    Serial controller for strategy phases.

    Each phase is a single child adapter (which can itself be a multi-strategy controller).
    """
    unit_contract_mode = "delegated"

    context_requires = ("generation",)
    context_provides = (KEY_PHASE, KEY_STRATEGY, KEY_STRATEGY_ID)
    context_mutates = ()
    context_cache = ()
    phase_out = (KEY_PHASE,)
    context_notes = ("Serial phase scheduler; delegates propose/update to active adapter.",)
    state_recovery_level = "L2"
    state_recovery_notes = "Restores current phase index, per-phase step counter, and child adapter states."
    population_state_mode = "delegate"

    def get_solution_pool_roots(self, control):
        # The chain stores schedule/cleanup state; candidate owners are children.
        return ()

    def __init__(
        self,
        phases: Optional[Sequence[SerialPhaseSpec]] = None,
        *,
        config: Optional[SerialStrategyConfig] = None,
        name: str = "serial_strategy_controller",
        priority: int = 0,
        **config_kwargs,
    ) -> None:
        super().__init__(name=name, priority=priority)
        self.config = self.resolve_config(
            config=config,
            config_cls=SerialStrategyConfig,
            config_kwargs=config_kwargs,
            adapter_name="StrategyChainAdapter",
        )
        self.cfg = self.config
        self.phases: List[SerialPhaseSpec] = list(phases or [])
        self._adapters: List[AlgorithmAdapter] = []
        self._phase_steps: List[int] = []
        self._current_idx: int = 0
        self._step_in_phase: int = 0
        self._population_owner_idx: int | None = None
        self._last_projection_writers: Dict[str, str] = {}
        self._pending_phase_retirements: list[int] = []
        self._phase_cleanup_control = None
        # Process-local acknowledgements. setup recreates child resources, so
        # these must not be replayed from a checkpoint as if resources stayed closed.
        self._retired_in_process: set[int] = set()

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------
    def setup(self, control: Any) -> None:
        self._materialize_adapters()
        self._phase_steps = [int(p.steps) for p in self.phases]
        self._current_idx = 0
        self._step_in_phase = 0
        self._population_owner_idx = None
        self._last_projection_writers = {}
        self._pending_phase_retirements = []
        self._phase_cleanup_control = control
        self._retired_in_process = set()
        # Every child that can receive checkpoint state must first establish
        # its clean baseline.  Restore is applied to the chain only after this
        # method returns, so lazily setting up a later restored phase would
        # either skip setup or erase its restored state on phase activation.
        for adapter in self._adapters:
            adapter.setup(control)

    def teardown(self, control: Any) -> None:
        failures = []
        for index, adapter in enumerate(self._adapters):
            if index in self._retired_in_process:
                continue
            try:
                adapter.teardown(control)
            except BaseException as exc:
                failures.append((str(adapter.name), exc))
            else:
                self._retired_in_process.add(index)
                if index in self._pending_phase_retirements:
                    self._pending_phase_retirements.remove(index)
        if failures:
            primary = failures[0][1]
            evidence = tuple({"participant": name, "error_type": type(exc).__name__,
                              "message": str(exc)} for name, exc in failures)
            from blackbase.project import attach_failure_evidence
            attach_failure_evidence(primary, "serial_adapter_teardown", evidence)
            raise primary

    # ------------------------------------------------------------------
    # Propose/Update
    # ------------------------------------------------------------------
    def propose(self, control: Any, context: Dict[str, Any]):
        adapter = self._current_adapter()
        if adapter is None:
            return []
        ctx = dict(context or {})
        ctx[KEY_PHASE] = self._current_phase_name()
        ctx[KEY_STRATEGY] = adapter.name
        ctx[KEY_STRATEGY_ID] = int(self._current_idx)
        return adapter.propose(control, ctx)

    def get_empty_proposal_outcome(
        self,
        control: Any,
        context: Dict[str, Any],
    ) -> Any | None:
        adapter = self._current_adapter()
        if adapter is None:
            return None
        ctx = dict(context)
        ctx[KEY_PHASE] = self._current_phase_name()
        ctx[KEY_STRATEGY] = adapter.name
        ctx[KEY_STRATEGY_ID] = int(self._current_idx)
        return child_empty_proposal_outcome(adapter, control, ctx)

    def update(
        self,
        control: Any,
        candidates: Sequence[np.ndarray],
        feedback: Any,
        context: Dict[str, Any],
    ) -> None:
        objectives, violations = feedback
        adapter = self._current_adapter()
        if adapter is None:
            return
        ctx = dict(context or {})
        # Provide commonly-needed runtime fields for advance_when.
        try:
            ctx.setdefault("generation", int(getattr(control, "generation", 0)))
        except Exception as _fallback_error:
            _report_optional_failure(component=__name__, event='StrategyChainAdapter.update.fallback_25', exc=_fallback_error)
            pass
        try:
            if "best_objective" not in ctx:
                ctx["best_objective"] = getattr(control, "best_objective", None)
        except Exception as _fallback_error:
            _report_optional_failure(component=__name__, event='StrategyChainAdapter.update.fallback_26', exc=_fallback_error)
            pass
        try:
            if "best_x" not in ctx:
                ctx["best_x"] = getattr(control, "best_x", None)
        except Exception as _fallback_error:
            _report_optional_failure(component=__name__, event='StrategyChainAdapter.update.fallback_27', exc=_fallback_error)
            pass
        try:
            if "evaluation_count" not in ctx:
                ctx["evaluation_count"] = getattr(control, "evaluation_count", None)
        except Exception as _fallback_error:
            _report_optional_failure(component=__name__, event='StrategyChainAdapter.update.fallback_28', exc=_fallback_error)
            pass
        ctx[KEY_PHASE] = self._current_phase_name()
        ctx[KEY_STRATEGY] = adapter.name
        ctx[KEY_STRATEGY_ID] = int(self._current_idx)
        owner_index = int(self._current_idx)
        adapter.update(control, candidates, feedback, ctx)
        self._population_owner_idx = owner_index

        self._step_in_phase += 1
        if self._should_advance(ctx):
            self._advance_phase(control)

    def on_proposal_repair(self, control, repair, context):
        self._forward_proposal_repair(control, repair, context)

    def proposal_repair_children(self, repair, context):
        adapter = self._current_adapter()
        if adapter is None:
            raise RuntimeError("proposal repair requires an active serial phase")
        ctx = dict(context)
        ctx[KEY_PHASE] = self._current_phase_name()
        ctx[KEY_STRATEGY] = adapter.name
        ctx[KEY_STRATEGY_ID] = int(self._current_idx)
        return ((adapter, repair, ctx),)

    def plan_repair_rejection_advance(self, control, report, owner_path):
        adapter = self._current_adapter()
        if adapter is None:
            return None
        path = f"{owner_path}/{self._current_idx}:{adapter.name}"
        if not any(row["owner_path"] == path or row["owner_path"].startswith(path + "/")
                   for row in report.get("failures", ())):
            return None
        child_plan = adapter.plan_repair_rejection_advance(control, report, path)
        if child_plan:
            return child_plan
        if self._current_idx + 1 >= len(self._adapters):
            return None
        expected = self._current_idx
        def apply():
            if self._current_idx != expected:
                raise RuntimeError("serial phase changed after repair advance planning")
            # Advancing a rejected attempt does not change the last population owner.
            if self._population_owner_idx is None:
                self._population_owner_idx = self._current_idx
            self._advance_phase(control)
        return (apply,)

    def _proposal_contexts(self, proposed_count, context):
        adapter = self._current_adapter()
        if adapter is None:
            raise RuntimeError("proposal contexts require an active serial phase")
        ctx = dict(context)
        ctx[KEY_PHASE], ctx[KEY_STRATEGY], ctx[KEY_STRATEGY_ID] = self._current_phase_name(), adapter.name, int(self._current_idx)
        return adapter.get_proposal_contexts(proposed_count, ctx)

    def on_proposal_disposition(
        self,
        control: Any,
        disposition: BatchDisposition,
        context: Dict[str, Any],
    ) -> None:
        adapter = self._current_adapter()
        if adapter is None:
            raise RuntimeError("proposal disposition requires an active serial phase")
        ctx = dict(context)
        ctx[KEY_PHASE] = self._current_phase_name()
        ctx[KEY_STRATEGY] = adapter.name
        ctx[KEY_STRATEGY_ID] = int(self._current_idx)
        adapter.on_proposal_disposition(control, disposition, ctx)

    # ------------------------------------------------------------------
    # State
    # ------------------------------------------------------------------
    def get_state(self) -> Dict[str, Any]:
        state = {
            "schema": "nsgablack.strategy_chain_state/v2",
            "current_idx": int(self._current_idx),
            "step_in_phase": int(self._step_in_phase),
            "phase_steps": list(self._phase_steps),
            "phase_names": [p.name for p in self.phases],
            "population_owner_idx": self._population_owner_idx,
            "pending_phase_retirements": list(self._pending_phase_retirements),
            "adapters": [],
        }
        for adapter in self._adapters:
            state["adapters"].append(adapter.get_state())
        state["population_partitions"] = [
            partition.as_dict() for partition in self.get_population_partitions()
        ]
        return state

    def set_state(self, state: Dict[str, Any]) -> None:
        self._materialize_adapters()
        schema = str(state.get("schema", "nsgablack.strategy_chain_state/v1"))
        if schema not in {
            "nsgablack.strategy_chain_state/v1",
            "nsgablack.strategy_chain_state/v2",
        }:
            raise ValueError(f"unsupported StrategyChainAdapter state schema: {schema}")
        saved_names = tuple(str(item) for item in state.get("phase_names", ()))
        current_names = tuple(str(phase.name) for phase in self.phases)
        if saved_names and saved_names != current_names:
            raise ValueError("StrategyChainAdapter phase identity mismatch")
        current_idx = int(state.get("current_idx", 0))
        if self._adapters and not 0 <= current_idx < len(self._adapters):
            raise ValueError("StrategyChainAdapter current phase is out of range")
        self._current_idx = current_idx
        self._step_in_phase = int(state.get("step_in_phase", 0))
        phase_steps = list(state.get("phase_steps", self._phase_steps))
        if len(phase_steps) != len(self.phases):
            raise ValueError("StrategyChainAdapter phase step schedule mismatch")
        self._phase_steps = [int(value) for value in phase_steps]
        raw_owner = state.get("population_owner_idx")
        owner = None if raw_owner is None else int(raw_owner)
        if owner is not None and not 0 <= owner < len(self._adapters):
            raise ValueError("StrategyChainAdapter population owner is out of range")
        self._population_owner_idx = owner
        self._restore_phase_retirements(state)
        adapter_states = tuple(state.get("adapters", ()) or ())
        if len(adapter_states) != len(self._adapters):
            raise ValueError("StrategyChainAdapter child state count mismatch")
        for adapter, astate in zip(self._adapters, adapter_states):
            adapter.set_state(dict(astate or {}))
        raw_partitions = tuple(state.get("population_partitions", ()) or ())
        if raw_partitions:
            self.set_population_partitions(
                tuple(PopulationPartition.from_dict(item) for item in raw_partitions)
            )

    def step_transaction_children(self) -> Sequence[AlgorithmAdapter]:
        self._materialize_adapters()
        return tuple(self._adapters)

    def snapshot_step_state(self) -> Mapping[str, Any]:
        return {
            "schema": "nsgablack.strategy_chain_step_transaction/v1",
            "current_idx": int(self._current_idx),
            "step_in_phase": int(self._step_in_phase),
            "phase_steps": list(self._phase_steps),
            "population_owner_idx": self._population_owner_idx,
            "pending_phase_retirements": list(self._pending_phase_retirements),
            "projection_writers": dict(self._last_projection_writers),
        }

    def restore_step_state(self, state: Mapping[str, Any]) -> None:
        if str(state.get("schema", "")) != "nsgablack.strategy_chain_step_transaction/v1":
            raise ValueError("unsupported StrategyChainAdapter step transaction schema")
        self._materialize_adapters()
        current_idx = int(state.get("current_idx", 0))
        if self._adapters and not 0 <= current_idx < len(self._adapters):
            raise ValueError("StrategyChainAdapter transaction phase is out of range")
        phase_steps = [
            int(value) for value in tuple(state.get("phase_steps", ()) or ())
        ]
        if len(phase_steps) != len(self.phases):
            raise ValueError("StrategyChainAdapter transaction schedule mismatch")
        raw_owner = state.get("population_owner_idx")
        owner = None if raw_owner is None else int(raw_owner)
        if owner is not None and not 0 <= owner < len(self._adapters):
            raise ValueError("StrategyChainAdapter transaction owner is out of range")
        self._current_idx = current_idx
        self._step_in_phase = int(state.get("step_in_phase", 0))
        self._phase_steps = phase_steps
        self._population_owner_idx = owner
        self._restore_phase_retirements(state)
        self._last_projection_writers = {
            str(key): str(value)
            for key, value in dict(state.get("projection_writers", {}) or {}).items()
        }

    def _population_owner(self) -> tuple[int, AlgorithmAdapter] | None:
        if not self._adapters:
            return None
        index = (
            int(self._current_idx)
            if self._population_owner_idx is None
            else int(self._population_owner_idx)
        )
        if index < 0 or index >= len(self._adapters):
            raise ValueError("StrategyChainAdapter population owner is out of range")
        return index, self._adapters[index]

    def resolve_population_state_mode(self) -> str:
        owner = self._population_owner()
        if owner is None:
            return "unresolved"
        _index, adapter = owner
        resolver = getattr(adapter, "resolve_population_state_mode", None)
        return str(resolver()) if callable(resolver) else "unresolved"

    def supported_population_state_modes(self) -> frozenset[str]:
        modes: set[str] = set()
        for adapter in self._adapters:
            resolver = getattr(adapter, "supported_population_state_modes", None)
            if callable(resolver):
                modes.update(str(item) for item in resolver())
        return frozenset(modes)

    def _population_prefix(self, index: int) -> str:
        phase_name = (
            self.phases[index].name
            if 0 <= int(index) < len(self.phases)
            else str(index)
        )
        return f"phase:{int(index)}:{phase_name}"

    def get_population_snapshot(
        self,
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray] | None:
        owner = self._population_owner()
        if owner is None:
            return None
        _index, adapter = owner
        getter = getattr(adapter, "get_population_snapshot", None)
        if not callable(getter):
            return None
        return getter()

    def set_population_snapshot(
        self,
        population: np.ndarray,
        objectives: np.ndarray,
        violations: np.ndarray,
    ) -> bool:
        owner = self._population_owner()
        if owner is None:
            return False
        _index, adapter = owner
        setter = getattr(adapter, "set_population_snapshot", None)
        if not callable(setter):
            return False
        return bool(setter(population, objectives, violations))

    def get_population_candidate_tokens(self) -> tuple[str | None, ...] | None:
        owner = self._population_owner()
        if owner is None:
            return None
        _index, adapter = owner
        getter = getattr(adapter, "get_population_candidate_tokens", None)
        return getter() if callable(getter) else None

    def set_population_candidate_tokens(
        self,
        candidate_tokens: Sequence[str | None],
    ) -> bool:
        owner = self._population_owner()
        if owner is None:
            return False
        _index, adapter = owner
        setter = getattr(adapter, "set_population_candidate_tokens", None)
        return bool(setter(candidate_tokens)) if callable(setter) else False

    def get_population_partitions(self) -> tuple[PopulationPartition, ...]:
        owner = self._population_owner()
        if owner is None:
            return ()
        index, adapter = owner
        return prefixed_population_partitions(
            self._population_prefix(index),
            adapter,
        )

    def set_population_partitions(
        self,
        partitions: Sequence[PopulationPartition],
    ) -> bool:
        values = tuple(partitions or ())
        handled = False
        owner_index: int | None = None
        for index, adapter in enumerate(self._adapters):
            restored = restore_prefixed_population_partitions(
                self._population_prefix(index),
                adapter,
                values,
            )
            if restored:
                if owner_index is not None and owner_index != index:
                    raise ValueError(
                        "StrategyChainAdapter cannot restore multiple authoritative phases"
                    )
                owner_index = index
                handled = True
        if values and not handled:
            raise ValueError(
                "StrategyChainAdapter checkpoint contains no matching phase partition"
            )
        if owner_index is not None:
            self._population_owner_idx = owner_index
        return handled or not values

    def get_runtime_context_projection(self, solver: Any) -> RuntimeContextProjection:
        adapter = self._current_adapter()
        own_fields: Dict[str, Any] = {KEY_PHASE: self._current_phase_name()}
        children = ()
        if adapter is not None:
            own_fields[KEY_STRATEGY] = adapter.name
            own_fields[KEY_STRATEGY_ID] = int(self._current_idx)
            children = (
                (
                    "adapter.phase."
                    f"{self._current_phase_name()}:{adapter.__class__.__name__}",
                    adapter,
                ),
            )
        aggregation = aggregate_adapter_runtime_projections(
            solver,
            owner_source=f"adapter.{self.__class__.__name__}",
            own_fields=own_fields,
            children=children,
        )
        self._last_projection_writers = dict(aggregation.field_sources)
        return aggregation.projection

    def get_runtime_context_projection_sources(self, solver: Any) -> Dict[str, str]:
        del solver
        return dict(self._last_projection_writers)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------
    def _materialize_adapters(self) -> None:
        if self._adapters:
            return
        enabled = [p for p in self.phases if bool(p.enabled)]
        self.phases = enabled
        for idx, phase in enumerate(self.phases):
            adapter = phase.adapter
            if isinstance(adapter, AlgorithmAdapter):
                self._adapters.append(adapter)
            elif callable(adapter):
                self._adapters.append(
                    invoke_bound_once(
                        adapter,
                        (
                            CallCandidate(args=(idx,), label="phase_index"),
                            CallCandidate(label="empty"),
                        ),
                    )
                )
            else:
                raise TypeError("phase.adapter must be AlgorithmAdapter or factory")

        if not self.phases:
            self._adapters = []

    def _current_adapter(self) -> Optional[AlgorithmAdapter]:
        if not self._adapters:
            return None
        idx = max(0, min(int(self._current_idx), len(self._adapters) - 1))
        return self._adapters[idx]

    def _current_phase_name(self) -> str:
        if not self.phases:
            return "phase_0"
        idx = max(0, min(int(self._current_idx), len(self.phases) - 1))
        return str(self.phases[idx].name)

    def _should_advance(self, ctx: Dict[str, Any]) -> bool:
        if not self.phases:
            return False
        idx = max(0, min(int(self._current_idx), len(self.phases) - 1))
        cond = self.phases[idx].advance_when
        if callable(cond):
            try:
                if bool(cond(dict(ctx))):
                    return True
            except Exception:
                raise
        steps = int(self._phase_steps[idx]) if idx < len(self._phase_steps) else int(self.phases[idx].steps)
        if steps < 0:
            return False
        return self._step_in_phase >= steps

    def _advance_phase(self, control: Any) -> None:
        if not self.phases:
            return
        old_idx = int(self._current_idx)
        next_idx = old_idx + 1
        if next_idx >= len(self.phases):
            if not self.cfg.repeat_last:
                return
            next_idx = len(self.phases) - 1
        if next_idx == old_idx:
            self._step_in_phase = 0
            return
        # Retirement is cleanup after the schedule decision commits. Rollback
        # must never pretend it can reopen a torn-down Provider/session.
        self._phase_cleanup_control = control
        if old_idx not in self._pending_phase_retirements:
            self._pending_phase_retirements.append(old_idx)
        self._current_idx = next_idx
        self._step_in_phase = 0

    def _restore_phase_retirements(self, state):
        pending = list(state.get("pending_phase_retirements", ()))
        if (len(set(pending)) != len(pending)
                or any(type(index) is not int or not 0 <= index < len(self._adapters) for index in pending)):
            raise ValueError("invalid pending serial phase retirement indices")
        self._pending_phase_retirements = pending

    def commit_step_state(self, state):
        failures = []
        for index in tuple(self._pending_phase_retirements):
            try:
                self._adapters[index].teardown(self._phase_cleanup_control)
            except BaseException as exc:
                failures.append((index, exc))
            else:
                self._pending_phase_retirements.remove(index)
                self._retired_in_process.add(index)
        if failures:
            from blackbase.project import attach_failure_evidence
            error = RuntimeError("serial phase retirement cleanup failed; schedule remains applied")
            attach_failure_evidence(error, "serial_phase_retirement", tuple(
                {"phase_index": index, "error_type": type(exc).__name__, "message": str(exc)}
                for index, exc in failures))
            raise error from failures[0][1]
        return None
