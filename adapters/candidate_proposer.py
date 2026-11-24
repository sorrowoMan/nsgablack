"""Reusable Unit construction for simple Case-local candidate proposers."""
from __future__ import annotations

import copy
from blackbase.contracts import BatchDisposition
from .algorithm_adapter import AlgorithmAdapter
from ..units import UnitBinding, UnitBuildRequest, CANDIDATE_SCHEMA
from ..representation.unit_builders import CandidateUnitBuilder
from ..core.state.solution_pool import SolutionRef


class CandidateProposerAdapter(AlgorithmAdapter):
    """Base only: a Case still implements its proposal/update and retention.

    Subclasses with live candidates must declare get_solution_pool_roots.
    pool_refs_from_feedback extracts exact accepted versions for that explicit
    state; the base cannot infer which candidates a subclass keeps or discards.
    """
    unit_schema = CANDIDATE_SCHEMA
    unit_build_operations = ("fresh",)
    unit_contract_mode = "owned"
    context_requires = ()
    context_provides = ()
    context_mutates = ()
    context_cache = ()
    context_notes = "Builds candidate Units; passes context to candidate operators without owning context keys."
    state_recovery_level = "L1"
    state_recovery_notes = "Restores proposal Units, IDs and optional local NumPy RNG; subclasses own any other strategy state."

    def __init__(self, name="candidate_proposer", priority=0, *, unit_binding=None):
        super().__init__(name=name, priority=priority)
        self.set_unit_binding(unit_binding or UnitBinding(CandidateUnitBuilder()))
        self.proposal_units = ()
        self._unit_counter = 0

    def build_candidate_units(self, candidates, context):
        built = tuple(self.unit_binding.build(UnitBuildRequest(
            f"{self.name}:candidate:{self._unit_counter + index + 1}", candidate), context)
            for index, candidate in enumerate(candidates))
        self._unit_counter += len(built)
        self.proposal_units = built
        return [unit.to_candidate() for unit in built]

    @staticmethod
    def pool_refs_from_feedback(feedback):
        """Extract canonical accepted references; never infer identity by value."""
        items = getattr(feedback, "items", None)
        if items is None:
            raise ValueError("candidate pool retention requires rich accepted feedback")
        refs = []
        for item in items:
            value = item.info.get("accepted_solution_ref")
            if value is None:
                raise ValueError("candidate pool retention requires exact accepted solution references")
            refs.append(SolutionRef.from_dict(dict(value)))
        return tuple(refs)

    def on_proposal_repair(self, control, repair, context):
        if repair.proposed_count != len(self.proposal_units):
            raise ValueError("Proposal repair does not align with candidate Units")
        units = list(self.proposal_units)
        for row in repair.changed_rows:
            index = repair.proposal_indices[row]
            units[index] = self.unit_binding.build(UnitBuildRequest(
                units[index].unit_id, repair.after.semantic_states[row]), context)
        self.proposal_units = tuple(units)

    def on_proposal_disposition(self, control, disposition: BatchDisposition, context):
        if disposition.proposed_count != len(self.proposal_units):
            raise ValueError("Proposal disposition does not align with candidate Units")
        self.proposal_units = tuple(self.proposal_units[i] for i in disposition.accepted_indices)

    def get_state(self):
        rng = getattr(self, "_rng", getattr(self, "rng", None))
        return {"unit_contract": self.get_unit_contract(), "counter": self._unit_counter,
                "units": [self.unit_binding.dump(unit) for unit in self.proposal_units],
                "rng_state": None if rng is None else copy.deepcopy(rng.bit_generator.state)}

    def set_state(self, state):
        if not state:
            return
        if state.get("unit_contract") != self.get_unit_contract():
            raise ValueError("Candidate proposer Unit binding mismatch")
        units = tuple(self.unit_binding.restore(payload) for payload in state["units"])
        counter = int(state["counter"])
        if counter < 0:
            raise ValueError("Candidate Unit counter must be nonnegative")
        rng = getattr(self, "_rng", getattr(self, "rng", None))
        if rng is not None and state.get("rng_state") is not None:
            rng.bit_generator.state = copy.deepcopy(state["rng_state"])
        self.proposal_units = units
        self._unit_counter = counter
