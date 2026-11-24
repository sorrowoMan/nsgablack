"""Explicit compatibility fields over one Adapter-owned, on-demand Unit.

Subclasses implement *_algorithm_state for strategy state. This template keeps
custom Unit codecs in checkpoints and step rollback without copying services.
"""
from __future__ import annotations

from dataclasses import MISSING, fields
from types import MappingProxyType
from typing import Any
import numpy as np
from .algorithm_adapter import AlgorithmAdapter
from ..units.contracts import StructureBuildRequest, UnitBinding


class _InactiveUnitList(list):
    """An observable empty default cannot silently consume state changes."""

    def _reject(self, *args, **kwargs):
        raise RuntimeError("Unit is not initialized; call ensure_unit() before mutating its fields")

    append = extend = insert = pop = remove = clear = sort = reverse = _reject
    __setitem__ = __delitem__ = __iadd__ = __imul__ = _reject


class UnitField:
    """An old Adapter attribute is a view, never a duplicate Unit authority."""
    def __init__(self, name: str):
        self.name = name

    def __get__(self, instance, owner=None):
        if instance is None:
            return self
        unit = instance.algorithm_unit
        return instance._unit_field_default(self.name) if unit is None else getattr(unit, self.name)

    def __set__(self, instance, value):
        if getattr(instance, "_restoring_unit_authority", False):
            # The codec Unit is the restored fact. Compatibility checkpoint
            # fields can restore local bookkeeping, never overwrite that fact.
            return
        if instance.algorithm_unit is None and instance._is_unit_field_default(self.name, value):
            return
        setattr(instance.ensure_unit(), self.name, value)


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
        if unit is None:
            return None
        record = unit.candidate_feedback.get(self.name)
        if record is None:
            return None
        if record["dependencies"] != self.dependencies or record["revision"] != self._revision(unit):
            return None
        return record["value"]

    def __set__(self, instance, value):
        if getattr(instance, "_restoring_unit_authority", False):
            # Preserve dependency revisions too: a stale restored score must
            # remain stale instead of being rebound to changed Unit content.
            return
        if instance.algorithm_unit is None and value is None:
            return
        unit = instance.ensure_unit()
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
        self._unit_id = f"{name}:structure"
        self.algorithm_unit = None

    def setup(self, control):
        """Default fresh-run baseline for custom structure-backed Adapters."""
        self.reset_unit()

    def _unit_field_default(self, name):
        """Read an inactive compatibility field without constructing a Unit.

        Only the family's declared data defaults are exposed. Mutable defaults
        are fresh empty values, not a second writable state owner.
        """
        for item in fields(self.unit_builder_type.unit_type):
            if item.name == name:
                if item.default is not MISSING:
                    value = item.default
                elif item.default_factory is not MISSING:
                    value = item.default_factory()
                else:
                    break
                if isinstance(value, list):
                    return _InactiveUnitList(value)
                if isinstance(value, dict):
                    return MappingProxyType(value)
                if isinstance(value, np.ndarray):
                    return np.frombuffer(value.tobytes(), dtype=value.dtype).reshape(value.shape)
                return value
        raise AttributeError(f"{type(self).__name__}: Unit field {name!r} has no inactive default")

    def _is_unit_field_default(self, name, value):
        default = self._unit_field_default(name)
        if default is None:
            return value is None
        if isinstance(default, np.ndarray):
            return isinstance(value, np.ndarray) and value.shape == default.shape and np.array_equal(value, default)
        if isinstance(default, (tuple, list, MappingProxyType)) and not default:
            expected = dict if isinstance(default, MappingProxyType) else list if isinstance(default, list) else tuple
            return type(value) is expected and not value
        return type(value) is type(default) and value == default

    def ensure_unit(self):
        """Create this instance's structure once, at an actual execution need."""
        if self.algorithm_unit is None:
            if getattr(self, "_restoring_absent_unit", False):
                raise ValueError("An absent Unit checkpoint cannot contain active Unit fields")
            unit = self.unit_binding.build(StructureBuildRequest(self._unit_id))
            self.algorithm_unit = unit
        return self.algorithm_unit

    def get_unit_id(self):
        """Read the stable structure identity without allocating its data."""
        return self._unit_id if self.algorithm_unit is None else self.algorithm_unit.unit_id

    def get_population_partitions(self):
        # An inactive owner's numeric empty view is not an existing partition.
        # Publishing it would make composite commit write it back and activate
        # a child that has never received a task.
        if self.algorithm_unit is None:
            return ()
        return super().get_population_partitions()

    def init_candidate(self, control, context=None):
        self.ensure_unit()
        return super().init_candidate(control, context)

    def init_population(self, control, count, context=None):
        self.ensure_unit()
        return super().init_population(control, count, context)

    def set_unit_binding(self, binding):
        self._require_unit_binding(binding)
        if self.algorithm_unit is None:
            super().set_unit_binding(binding)
            return
        values = self._unit_values()
        new_unit = binding.build(StructureBuildRequest(self.algorithm_unit.unit_id, {"values": values}))
        super().set_unit_binding(binding)
        self.algorithm_unit = new_unit

    def _unit_values(self):
        # Only declared data fields; never traverse the Adapter object graph.
        unit = self.ensure_unit()
        return {f.name: getattr(unit, f.name) for f in fields(unit) if f.name != "unit_id"}

    def reset_unit(self):
        """Discard the old structure; construct a replacement only when needed."""
        if self.algorithm_unit is not None:
            self._unit_id = self.algorithm_unit.unit_id
        self.algorithm_unit = None

    def validate_local_unit_contract(self):
        from ..units.collections import PopulationUnit
        if isinstance(self.algorithm_unit, PopulationUnit):
            self.algorithm_unit.validate_member_contract()

    def preference_view(self, *, owner_path):
        """Expose one detached instance view without granting decision rights."""
        if self.algorithm_unit is None:
            return None
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
        if getattr(self, "_restoring_unit_authority", False):
            raise ValueError("An authoritative restored Unit cannot be rebuilt from compatibility state")
        if getattr(self, "_restoring_absent_unit", False):
            raise ValueError("An absent Unit checkpoint cannot rebuild an active structure")
        values = {} if self.algorithm_unit is None else self._unit_values()
        self.algorithm_unit = self.unit_binding.build(StructureBuildRequest(
            self.get_unit_id(), {"values": values, **parameters}, operation), context)
        return self.algorithm_unit

    def get_state(self):
        state = dict(self._get_algorithm_state())
        state["unit_contract"] = self.get_unit_contract()
        state["unit_id"] = self.get_unit_id()
        state["algorithm_unit"] = None if self.algorithm_unit is None else self.unit_binding.dump(self.algorithm_unit)
        bindings = self.operator_bindings_state()
        if bindings:
            state["operator_bindings"] = bindings
        return state

    def _restore_unit_envelope(self, state, *, step=False):
        if "unit_contract" in state and state["unit_contract"] != self.get_unit_contract():
            raise ValueError("Saved Unit binding/schema differs from the configured binding")
        saved = state.get("algorithm_unit")
        restore = self.unit_binding.restore_step if step else self.unit_binding.restore
        unit = restore(saved) if saved is not None else None
        unit_id = state.get("unit_id", self.get_unit_id() if unit is None else unit.unit_id)
        if not isinstance(unit_id, str) or not unit_id.strip() or (unit is not None and unit.unit_id != unit_id):
            raise ValueError("Saved Unit identity does not match its structure")
        return unit, unit_id

    def set_state(self, state):
        unit, unit_id = self._restore_unit_envelope(state)
        with self.restoring_operator_bindings(state.get("operator_bindings", {})):
            previous = self.algorithm_unit
            previous_id = self._unit_id
            self.algorithm_unit = unit
            self._restoring_absent_unit = "algorithm_unit" in state and unit is None
            self._restoring_unit_authority = unit is not None
            try:
                self._set_algorithm_state(state)
                self._unit_id = unit_id
                if unit is not None:
                    self._after_unit_restore()
            except BaseException:
                self.algorithm_unit = previous
                self._unit_id = previous_id
                raise
            finally:
                self._restoring_absent_unit = False
                self._restoring_unit_authority = False

    def _after_unit_restore(self):
        """Refresh derived views after codec data replaces compatibility fields."""
        return None

    def snapshot_step_state(self):
        snapshot = getattr(self, "_snapshot_algorithm_step_state", None)
        if snapshot is None:
            return super().snapshot_step_state()
        state = dict(snapshot())
        state["unit_contract"] = self.get_unit_contract()
        state["unit_id"] = self.get_unit_id()
        state["algorithm_unit"] = None if self.algorithm_unit is None else self.unit_binding.snapshot_step(self.algorithm_unit)
        bindings = self.operator_bindings_state()
        if bindings:
            state["operator_bindings"] = bindings
        return state

    def restore_step_state(self, state):
        restore = getattr(self, "_restore_algorithm_step_state", None)
        if restore is None:
            return super().restore_step_state(state)
        unit, unit_id = self._restore_unit_envelope(state, step=True)
        with self.restoring_operator_bindings(state.get("operator_bindings", {})):
            self.algorithm_unit = unit
            self._restoring_absent_unit = "algorithm_unit" in state and unit is None
            self._restoring_unit_authority = unit is not None
            try:
                restore(state)
            finally:
                # Provider cleanup failures must not lose the restored structure.
                self.algorithm_unit = unit
                self._unit_id = unit_id
                self._restoring_absent_unit = False
                try:
                    if unit is not None:
                        self._after_unit_restore()
                finally:
                    self._restoring_unit_authority = False

    def _get_algorithm_state(self):
        return {}

    def _set_algorithm_state(self, state):
        pass
