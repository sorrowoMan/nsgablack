"""Explicit compatibility fields over one pipeline-built authoritative Unit.

Subclasses implement *_algorithm_state for strategy state. This template keeps
custom Unit codecs in checkpoints and step rollback without copying services.
"""
from __future__ import annotations

from dataclasses import fields
from typing import Any
from .algorithm_adapter import AlgorithmAdapter
from ..units.contracts import StructureBuildRequest, UnitBinding


class UnitField:
    """An old Adapter attribute is a view, never a duplicate Unit authority."""
    def __init__(self, name: str):
        self.name = name

    def __get__(self, instance, owner=None):
        if instance is None:
            return self
        return getattr(instance.algorithm_unit, self.name)

    def __set__(self, instance, value):
        setattr(instance.algorithm_unit, self.name, value)


class UnitFeedbackField:
    """Scalar selection feedback tied to explicit candidate content in the Unit.

    A stale value reads as absent; it cannot rank a changed candidate. The
    record and revision travel together through the Unit codec. This is the
    owner's assertion of association, not proof of an objective evaluation.
    """
    def __init__(self, *dependencies):
        self.dependencies = tuple(dependencies)

    def __set_name__(self, owner, name):
        self.name = name

    def _revision(self, unit):
        from ..units.features import _signature
        return _signature({name: getattr(unit, name) for name in self.dependencies})

    def __get__(self, instance, owner=None):
        if instance is None:
            return self
        unit = instance.algorithm_unit
        record = unit.candidate_feedback.get(self.name)
        if record is None:
            return None
        if record["dependencies"] != self.dependencies or record["revision"] != self._revision(unit):
            return None
        return record["value"]

    def __set__(self, instance, value):
        unit = instance.algorithm_unit
        records = dict(unit.candidate_feedback)
        if value is None:
            records.pop(self.name, None)
        else:
            records[self.name] = dict(value=float(value), dependencies=self.dependencies,
                                      revision=self._revision(unit))
        unit.candidate_feedback = records


class UnitBackedAdapter(AlgorithmAdapter):
    state_recovery_level = "L0"
    state_recovery_notes = "Unit codec template; concrete Adapters declare their strategy recovery level."
    context_requires = ()
    context_provides = ()
    context_mutates = ()
    context_cache = ()
    unit_builder_type = None
    unit_contract_mode = "owned"
    unit_build_operations = ("initialize",)
    accepts_proposal_replacement = False
    # Disposition owns these coordinates; a later UnitRepair projection cannot
    # compact, reorder or overwrite them a second time.
    admission_unit_fields = ()

    def __init__(self, name: str, priority: int = 0, *, unit_binding=None):
        super().__init__(name=name, priority=priority)
        AlgorithmAdapter.set_unit_binding(self, unit_binding or UnitBinding(self.unit_builder_type()))
        self.algorithm_unit = self.unit_binding.build(StructureBuildRequest(f"{name}:structure"))

    def set_unit_binding(self, binding):
        self._require_unit_binding(binding)
        values = self._unit_values()
        new_unit = binding.build(StructureBuildRequest(self.algorithm_unit.unit_id, {"values": values}))
        super().set_unit_binding(binding)
        self.algorithm_unit = new_unit

    def _unit_values(self):
        # Only declared data fields; never traverse the Adapter object graph.
        return {f.name: getattr(self.algorithm_unit, f.name) for f in fields(self.algorithm_unit) if f.name != "unit_id"}

    def reset_unit(self):
        """Fresh-run construction; restore later replaces it through the codec."""
        self.algorithm_unit = self.unit_binding.build(StructureBuildRequest(self.algorithm_unit.unit_id))

    def validate_local_unit_contract(self):
        from ..units.collections import PopulationUnit
        if isinstance(self.algorithm_unit, PopulationUnit):
            self.algorithm_unit.validate_member_contract()

    def preference_view(self, *, owner_path):
        """Expose one detached instance view without granting decision rights."""
        from ..units.views import UnitView, PopulationView
        view_type = PopulationView if "population" in self.unit_binding.schema.required_fields else UnitView
        return view_type.capture(self.algorithm_unit, self.unit_binding, owner_path=owner_path)

    @staticmethod
    def member_inputs_for(control, candidates):
        """Project existing semantic/provenance records for structural maintenance.

        No identities are allocated and no search policy is applied here. The
        PopulationChange capture detaches these invocation-local data records.
        """
        from blackbase.types import UnknownState
        resolver = getattr(control, "candidate_provenance_for", None)
        semantic = getattr(control, "semantic_candidate_state", None)
        metadata, provenance = [], []
        for index, candidate in enumerate(candidates):
            record = resolver(candidate) if callable(resolver) else None
            indexed = record is None and callable(resolver)
            if indexed:
                record = resolver(candidate, candidate_index=index)
            export = getattr(record, "as_dict", None)
            provenance.append(export() if callable(export) else None)
            state = candidate if isinstance(candidate, UnknownState) else None
            if state is None and callable(semantic) and record is not None:
                state = semantic(candidate, **({"candidate_index": index} if indexed else {}))
            metadata.append(dict(state.metadata) if isinstance(state, UnknownState) else {})
        return dict(candidate_metadata=tuple(metadata), candidate_provenance=tuple(provenance))

    def rebuild_unit(self, operation: str, *, context=None, **parameters):
        self.algorithm_unit = self.unit_binding.build(StructureBuildRequest(
            self.algorithm_unit.unit_id, {"values": self._unit_values(), **parameters}, operation), context)
        return self.algorithm_unit

    def get_state(self):
        state = dict(self._get_algorithm_state())
        state["algorithm_unit"] = self.unit_binding.dump(self.algorithm_unit)
        return state

    def set_state(self, state):
        saved = state.get("algorithm_unit")
        unit = self.unit_binding.restore(saved) if saved is not None else None
        self._set_algorithm_state(state)
        if unit is not None:
            self.algorithm_unit = unit
            self._after_unit_restore()

    def _after_unit_restore(self):
        """Refresh derived views after codec data replaces compatibility fields."""
        return None

    def snapshot_step_state(self):
        snapshot = getattr(self, "_snapshot_algorithm_step_state", None)
        if snapshot is None:
            return super().snapshot_step_state()
        state = dict(snapshot())
        state["algorithm_unit"] = self.unit_binding.dump(self.algorithm_unit)
        return state

    def restore_step_state(self, state):
        restore = getattr(self, "_restore_algorithm_step_state", None)
        if restore is None:
            return super().restore_step_state(state)
        saved = state.get("algorithm_unit")
        unit = self.unit_binding.restore(saved) if saved is not None else None
        try:
            restore(state)
        finally:
            # Provider cleanup failures must not lose the restored structure.
            if unit is not None:
                self.algorithm_unit = unit
                self._after_unit_restore()

    def _get_algorithm_state(self):
        return {}

    def _set_algorithm_state(self, state):
        pass
