"""An elite wrapper creates its archive only when it receives actual members."""
from __future__ import annotations

import numpy as np

from nsgablack.adapters import AlgorithmAdapter, EliteRetentionAdapter, EliteRetentionConfig
from nsgablack.core.evaluation_feedback import OptimizationFeedbackBatch
from nsgablack.representation import ArchiveUnitBuilder
from nsgablack.units import UnitBinding


class Inner(AlgorithmAdapter):
    def __init__(self):
        super().__init__("inner")

    def propose(self, control, context):
        return ()

    def update(self, control, candidates, feedback, context):
        pass

    def get_state(self):
        return {}

    def set_state(self, state):
        pass


class Control:
    def fork_rng(self, name):
        return np.random.default_rng(7)


class ObservedArchiveBuilder(ArchiveUnitBuilder):
    def __init__(self, calls):
        self.calls = calls

    def build(self, request, context=None):
        self.calls.append("build")
        return super().build(request, context)

    def restore(self, payload):
        self.calls.append("restore")
        return super().restore(payload)


def wrapper():
    calls = []
    adapter = EliteRetentionAdapter(Inner(), EliteRetentionConfig(history_size=3),
        unit_binding=UnitBinding(ObservedArchiveBuilder(calls)))
    return adapter, calls


def add(adapter, value):
    adapter.update(Control(), (np.array([value]),),
        OptimizationFeedbackBatch.from_arrays([[value]], [0.0]), {})


def test_elite_setup_reporting_and_empty_feedback_do_not_create_archive():
    adapter, calls = wrapper()
    adapter.setup(Control())
    adapter.get_state()
    adapter.snapshot_step_state()
    adapter.get_runtime_context_projection(Control())
    adapter.update(Control(), (), OptimizationFeedbackBatch.from_arrays(
        np.empty((0, 1)), np.empty(0)), {})
    assert adapter.algorithm_unit is None
    assert calls == []


def test_first_elite_feedback_creates_archive_once_and_keeps_members():
    adapter, calls = wrapper()
    adapter.setup(Control())
    add(adapter, 3.0)
    unit = adapter.algorithm_unit
    add(adapter, 1.0)
    assert adapter.algorithm_unit is unit
    assert calls == ["build"]
    assert [entry["score"] for entry in unit.entries] == [1.0, 3.0]


def test_first_elite_activation_rolls_back_to_absence():
    adapter, calls = wrapper()
    adapter.setup(Control())
    transaction = adapter.begin_step_transaction()
    add(adapter, 4.0)
    assert adapter.algorithm_unit is not None
    transaction.rollback()
    assert adapter.algorithm_unit is None
    assert adapter._archive == []
    assert calls == ["build"]
    add(adapter, 2.0)
    assert calls == ["build", "build"]
    assert [entry["score"] for entry in adapter.algorithm_unit.entries] == [2.0]


def test_elite_checkpoint_restores_archive_without_constructing_again():
    source, _ = wrapper()
    source.setup(Control())
    add(source, 3.0)
    saved = source.get_state()
    restored, calls = wrapper()
    restored.setup(Control())
    restored.set_state(saved)
    unit = restored.algorithm_unit
    assert calls == ["restore"]
    add(restored, 1.0)
    assert restored.algorithm_unit is unit
    assert calls == ["restore"]
    assert [entry["score"] for entry in unit.entries] == [1.0, 3.0]
