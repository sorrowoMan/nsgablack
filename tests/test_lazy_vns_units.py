"""VNS defers both candidate and neighborhood Units until an algorithm need."""
from __future__ import annotations

import copy
import json

import numpy as np
import pytest

from nsgablack.adapters import VNSAdapter
from nsgablack.context_keys import KEY_MUTATION_SIGMA, KEY_VNS_K
from nsgablack.core.evaluation_feedback import OptimizationFeedbackBatch
from nsgablack.representation import (
    CandidateUnitBuilder, ContextGaussianMutation, NeighborhoodUnitBuilder,
    RepresentationPipeline,
)
from nsgablack.units import UnitBinding


class Control:
    representation_pipeline = RepresentationPipeline(mutator=ContextGaussianMutation())

    def init_candidate(self, context):
        return np.array([4.0])

    def mutate_candidate(self, candidate, context):
        return np.asarray(candidate) - context[KEY_MUTATION_SIGMA]


class ObservedCandidateBuilder(CandidateUnitBuilder):
    def __init__(self, events):
        self.events = events

    def build(self, request, context=None):
        self.events.append(("candidate", "build"))
        return super().build(request, context)

    def restore(self, payload):
        self.events.append(("candidate", "restore"))
        return super().restore(payload)


class ObservedNeighborhoodBuilder(NeighborhoodUnitBuilder):
    def __init__(self, events):
        self.events = events

    def build(self, request, context=None):
        self.events.append(("neighborhood", "build"))
        return super().build(request, context)

    def construct(self, values, operation, parameters, context):
        super().construct(values, operation, parameters, context)
        # Distinct custom geometry proves reporting/restore cannot reproduce
        # the default schedule from VNSConfig instead of using the real Unit.
        values["scales"] = (0.3, 0.9)

    def restore(self, payload):
        self.events.append(("neighborhood", "restore"))
        return super().restore(payload)


def adapter():
    events = []
    value = VNSAdapter(batch_size=2, k_max=1,
        unit_binding=UnitBinding(ObservedCandidateBuilder(events)),
        neighborhood_binding=UnitBinding(ObservedNeighborhoodBuilder(events)))
    return value, events


def accept_baseline(value, control):
    candidates = value.propose(control, {})
    value.update(control, candidates, OptimizationFeedbackBatch.from_arrays([[16.0]], [0.0]), {})


def test_vns_constructor_setup_reporting_and_inactive_restart_build_no_units():
    value, events = adapter()
    control = Control()
    value.setup(control)
    value.get_unit_contracts()
    value.validate_unit_bindings()
    value.get_state()
    value.snapshot_step_state()
    assert value._proposal_contexts(0, {}) == ()
    assert value.get_runtime_context_projection(control) == {}
    value.restart_search(control, {})
    assert value.get_runtime_context_projection(control) == {}
    assert value.current_unit is None and value.neighborhood_unit is None
    assert events == []


def test_first_vns_proposal_creates_geometry_once_and_restart_reuses_it():
    value, events = adapter()
    control = Control()
    value.setup(control)
    accept_baseline(value, control)
    neighborhood = value.neighborhood_unit
    value.propose(control, {})
    assert events.count(("neighborhood", "build")) == 1
    assert value.get_runtime_context_projection(control)[KEY_MUTATION_SIGMA] == 0.3
    value.restart_search(control, {})
    assert value.neighborhood_unit is neighborhood
    assert value.current_unit is None
    value.propose(control, {})
    assert value.neighborhood_unit is neighborhood
    assert events.count(("neighborhood", "build")) == 1


def test_inactive_vns_checkpoint_restores_absence_without_any_builder_calls():
    source, _ = adapter()
    source.setup(Control())
    saved = json.loads(json.dumps(source.get_state()))
    assert saved["neighborhood_unit"] is None and saved["current_unit"] is None
    clone, events = adapter()
    clone.setup(Control())
    clone.set_state(saved)
    assert clone.neighborhood_unit is None and clone.current_unit is None
    assert clone.get_runtime_context_projection(Control()) == {}
    assert events == []


def test_first_vns_activation_rolls_back_both_units_to_absence():
    value, events = adapter()
    value.setup(Control())
    transaction = value.begin_step_transaction()
    value.propose(Control(), {})
    assert value.neighborhood_unit is not None and value.current_unit is not None
    transaction.rollback()
    assert value.neighborhood_unit is None and value.current_unit is None
    assert value._pending_units == [] and value._unit_counter == 0
    assert value.get_runtime_context_projection(Control()) == {}
    assert events == [("neighborhood", "build"), ("candidate", "build")]


def test_active_vns_checkpoint_uses_only_codecs_and_keeps_custom_geometry():
    source, _ = adapter()
    source.setup(Control())
    accept_baseline(source, Control())
    source.k = 1
    clone, events = adapter()
    clone.setup(Control())
    clone.set_state(json.loads(json.dumps(source.get_state())))
    assert events == [("neighborhood", "restore"), ("candidate", "restore")]
    assert clone._current_sigma() == 0.9
    assert clone.get_runtime_context_projection(Control()) == {KEY_VNS_K: 1, KEY_MUTATION_SIGMA: 0.9}
    clone.propose(Control(), {})
    assert ("neighborhood", "build") not in events
    assert ("candidate", "build") in events


@pytest.mark.parametrize("missing", [False, True])
@pytest.mark.parametrize("activity", ["candidate", "pending", "neighborhood", "score"])
def test_missing_vns_geometry_rejects_active_state_without_building(missing, activity):
    value, events = adapter()
    value.setup(Control())
    saved = copy.deepcopy(value.get_state())
    if activity in {"candidate", "pending"}:
        source, _ = adapter()
        source.setup(Control())
        source.propose(Control(), {})
        saved = copy.deepcopy(source.get_state())
        if activity == "pending":
            saved["current_unit"] = saved["current_x"] = None
    elif activity == "neighborhood":
        saved["k"] = 1
    else:
        saved["current_score"] = 1.0
    if missing:
        saved.pop("neighborhood_unit")
    else:
        saved["neighborhood_unit"] = None
    with pytest.raises(ValueError, match="requires its saved neighborhood Unit"):
        value.set_state(saved)
    assert value.neighborhood_unit is None and value.current_unit is None
    assert all(operation != "build" for _, operation in events)


def test_numeric_vns_legacy_restore_requires_explicit_codec_migration():
    value, events = adapter()
    saved = value.get_state()
    saved.pop("current_unit")
    saved.pop("neighborhood_unit")
    saved["current_x"] = [4.0]
    with pytest.raises(ValueError, match="legacy numerical checkpoint.*explicit Unit codec migration"):
        value.set_state(saved)
    assert events == []


def test_fresh_vns_setup_discards_units_without_eager_reconstruction():
    value, events = adapter()
    control = Control()
    value.setup(control)
    value.propose(control, {})
    count = len(events)
    value.setup(control)
    assert value.current_unit is None and value.neighborhood_unit is None
    assert value.get_runtime_context_projection(control) == {}
    assert len(events) == count


def test_inactive_vns_restore_rejects_changed_auxiliary_binding_without_building():
    source, _ = adapter()
    saved = source.get_state()
    clone, events = adapter()
    clone.neighborhood_binding = UnitBinding(ObservedNeighborhoodBuilder(events), name="other/geometry")
    with pytest.raises(ValueError, match="Unit binding mismatch"):
        clone.set_state(saved)
    assert events == []


@pytest.mark.parametrize("parameter,value", [
    ("k_max", 2), ("base_sigma", 0.4), ("scale", 3.0), ("max_sigma", 5.0),
])
def test_inactive_vns_restore_rejects_changed_deferred_parameters_without_building(parameter, value):
    source, _ = adapter()
    clone, events = adapter()
    setattr(clone.cfg, parameter, value)
    with pytest.raises(ValueError, match="construction parameters mismatch"):
        clone.set_state(source.get_state())
    assert events == []


@pytest.mark.parametrize("missing", ["unit_contract", "neighborhood_parameters"])
def test_explicit_absent_vns_geometry_requires_complete_construction_identity(missing):
    value, events = adapter()
    saved = value.get_state()
    saved.pop(missing)
    with pytest.raises(ValueError, match="requires binding and neighborhood construction identity"):
        value.set_state(saved)
    assert events == []


def test_preexisting_active_vns_codec_without_parameter_identity_restores_without_building():
    source, _ = adapter()
    source.setup(Control())
    accept_baseline(source, Control())
    saved = source.get_state()
    saved.pop("neighborhood_parameters")
    clone, events = adapter()
    clone.set_state(saved)
    assert clone._current_sigma() == 0.3
    assert all(operation == "restore" for _, operation in events)
