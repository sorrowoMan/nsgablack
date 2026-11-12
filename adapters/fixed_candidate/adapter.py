"""Evaluate one representation-owned candidate without inventing a search loop."""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from blackbase.contracts import ComponentContract

from ..algorithm_adapter import AlgorithmAdapter
from ...units import UnitBinding, UnitBuildRequest, CANDIDATE_SCHEMA
from ...representation.unit_builders import CandidateUnitBuilder
from ...core.state.solution_pool import SolutionRef


class FixedCandidateAdapter(AlgorithmAdapter):
    """Provider-neutral strategy for one-shot evaluation Cases.

    Its configured initializer or the shared candidate pipeline supplies the
    candidate, while the Problem owns its meaning. This Adapter routes it through the canonical NSGABlack
    lifecycle, so diagnostic and validation Cases do not need a private
    control loop.
    """
    operation_methods = {"initializer": "initialize"}
    unit_build_operations = ("fresh",)
    pool_input_modes = ("initialize",)

    def default_pool_input_count(self):
        return 1

    method_ids = ("evaluation.fixed",)
    context_requires = ()
    context_optional = ()
    context_provides = ()
    context_mutates = ()
    context_cache = ()
    context_notes = (
        "Requests and evaluates one initialized candidate per solver step.",
        "Does not mutate, fit, sample, or select a backend.",
    )
    state_recovery_level = "L0"
    state_recovery_notes = "Restores current candidate Unit and construction identity; evaluation authority remains with Solver."
    contract = ComponentContract(
        name="fixed_candidate",
        supports_gradient=False,
        supports_batch=False,
        supports_resume=True,
        metadata={
            "family": "one_shot",
            "provider_neutral": True,
            "method_ids": method_ids,
        },
    )

    unit_schema = CANDIDATE_SCHEMA
    unit_contract_mode = "owned"

    def __init__(self, name: str = "fixed_candidate", priority: int = 0, *,
                 unit_binding=None, initializer=None) -> None:
        super().__init__(name=name, priority=priority)
        self.set_initializer(initializer)
        self.set_unit_binding(unit_binding or UnitBinding(CandidateUnitBuilder()))
        self.current_unit = None
        self._unit_counter = 0
        self._current_pool_ref = None

    def setup(self, control):
        if self.get_local_operator_bindings():
            self.seed_operator_bindings(self.create_local_rng(control))
        self.current_unit = None
        self._unit_counter = 0
        self._current_pool_ref = None

    def propose(self, control: Any, context: Mapping[str, Any]) -> Sequence[Any]:
        candidate = self.init_candidate(control, context)
        if self.get_bound_initializer() is not None:
            # init_candidate returns a numeric view. Recover the retained
            # semantic envelope before Unit construction, so normalization of
            # this proposal cannot replace initialization metadata with {}.
            candidate = self.semantic_proposal(control, candidate)
        unit = self.unit_binding.build(UnitBuildRequest(
            f"{self.name}:candidate:{self._unit_counter + 1}", candidate), context)
        self.current_unit = unit
        self._current_pool_ref = None
        self._unit_counter += 1
        proposed = unit.to_candidate()
        lookup = getattr(control, "candidate_provenance_for", None)
        provenance = lookup(candidate) if callable(lookup) else None
        if provenance is not None:
            control.bind_candidate_provenance((proposed,), (provenance,), activate=False)
        return (proposed,)

    def get_state(self):
        state = {"counter": self._unit_counter, "unit_contract": self.get_unit_contract(),
                "current_pool_ref": None if self._current_pool_ref is None else self._current_pool_ref.as_dict(),
                "unit": None if self.current_unit is None else self.unit_binding.dump(self.current_unit)}
        bindings = self.operator_bindings_state()
        if bindings:
            state["operator_bindings"] = bindings
        return state

    def set_state(self, state):
        saved = None if state is None else state.get("operator_bindings", {})
        with self.restoring_operator_bindings(saved):
            self._restore_candidate_state(state)

    def _restore_candidate_state(self, state):
        if not state:
            return
        if state.get("unit_contract") != self.get_unit_contract():
            raise ValueError("Fixed candidate Unit binding mismatch")
        unit = None if state["unit"] is None else self.unit_binding.restore(state["unit"])
        value = state.get("current_pool_ref")
        ref = None if value is None else SolutionRef.from_dict(dict(value))
        if ref is not None and unit is None:
            raise ValueError("fixed candidate reference requires a current Unit")
        self.current_unit = unit
        self._current_pool_ref = ref
        self._unit_counter = int(state["counter"])

    def get_solution_pool_roots(self, control):
        if self.current_unit is None:
            return ()
        return None if self._current_pool_ref is None else (self._current_pool_ref,)

    def update(
        self,
        control: Any,
        candidates: Sequence[Any],
        feedback: Any,
        context: Mapping[str, Any],
    ) -> None:
        if len(tuple(candidates)) != 1:
            raise ValueError("FixedCandidateAdapter requires exactly one candidate")
        objectives, violations = feedback
        if len(objectives) != 1 or len(violations) != 1:
            raise ValueError("FixedCandidateAdapter requires exactly one feedback row")
        items = getattr(feedback, "items", ())
        value = items[0].info.get("accepted_solution_ref") if items else None
        self._current_pool_ref = None if value is None else SolutionRef.from_dict(dict(value))
        # The canonical repair may have changed the proposal. Keep its actual
        # accepted semantic value beside the exact pool version.
        candidate = candidates[0]
        if self._current_pool_ref is not None:
            candidate = control.solution_pool.read((self._current_pool_ref,), allow_pending=True).semantic_states[0]
        self.current_unit = self.unit_binding.build(UnitBuildRequest(
            f"{self.name}:candidate:{self._unit_counter}", candidate), context)


__all__ = ["FixedCandidateAdapter"]
