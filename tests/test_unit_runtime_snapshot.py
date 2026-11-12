import threading
from dataclasses import dataclass, field
import json
import numpy as np
import pytest

from nsgablack.units import PopulationChange
from nsgablack.units import UnitBinding, PopulationUnit, StructureBuildRequest, UnitSchema
from nsgablack.representation import PopulationUnitBuilder


@dataclass
class ExtendedPopulation(PopulationUnit):
    ages: np.ndarray = field(default_factory=lambda: np.zeros(0))
    notes: dict = field(default_factory=dict)
    schema = UnitSchema("test.step_population", required_fields=(*PopulationUnit.schema.required_fields,
        "ages", "notes"), candidate_projection=False)


class ExtendedBuilder(PopulationUnitBuilder):
    unit_type = ExtendedPopulation


def populated(binding=None):
    binding = binding or UnitBinding(ExtendedBuilder())
    unit = binding.build(StructureBuildRequest("unit"))
    unit.initialize_population([[1., 2.], [3., 4.]], [[1.], [2.]], [0., 0.], candidate_tokens=("a", "b"))
    unit.ages = np.array([2, 7])
    unit.notes = {"nested": ["original"], "keyed": {(b"k", 2): np.array([5.])}}
    return binding, unit


def test_member_change_detaches_without_computing_a_digest(monkeypatch):
    from nsgablack.units import features
    def forbidden(*args, **kwargs):
        pytest.fail("member notification must not compute an unused hash")
    monkeypatch.setattr(features.hashlib, "sha256", forbidden)
    x = np.array([[1., 2.]])
    metadata = {"labels": ["original"]}
    change = PopulationChange("replacement", 1, 1, (None,), (0,),
        incoming_population=x, incoming_objectives=[[3.]], incoming_violations=[0.],
        incoming_tokens=("token",), incoming_metadata=(metadata,))
    x[:] = 100
    metadata["labels"].append("changed")
    np.testing.assert_array_equal(change.incoming_population, [[1., 2.]])
    assert change.incoming_metadata[0]["labels"] == ("original",)
    with pytest.raises(ValueError):
        change.incoming_population.setflags(write=True)
    with pytest.raises(TypeError):
        change.incoming_metadata[0]["new"] = 1


def test_native_step_snapshot_preserves_fields_and_repeat_restore_isolation(monkeypatch):
    binding, unit = populated()
    checkpoint = binding.dump(unit)
    saved = binding.snapshot_step(unit)
    assert isinstance(saved["payload"]["population"], np.ndarray)
    assert isinstance(saved["payload"]["ages"], np.ndarray)
    unit.population[:] = 99
    unit.ages[:] = -1
    unit.notes["nested"].append("changed")
    monkeypatch.setattr(binding.builder, "build", lambda *a, **k: pytest.fail("restore cannot build"))
    restored = binding.restore_step(saved)
    assert binding.dump(restored) == checkpoint
    restored.population[:] = 300
    restored.notes["nested"].append("another")
    assert binding.dump(binding.restore_step(saved)) == checkpoint
    assert "step_schema" not in checkpoint
    assert binding.dump(binding.restore(json.loads(json.dumps(checkpoint)))) == checkpoint


def test_custom_persistent_codec_is_not_bypassed():
    class Custom(ExtendedBuilder):
        def dump(self, unit):
            return {"wrapped": super().dump(unit)}
        def restore(self, saved):
            return super().restore(saved["wrapped"])
    binding, unit = populated(UnitBinding(Custom()))
    saved = binding.snapshot_step(unit)
    assert "step_schema" not in saved
    assert "wrapped" in saved["payload"]
    assert binding.dump(binding.restore_step(saved)) == binding.dump(unit)


def test_instance_customization_uses_persistent_path_and_native_binding_is_checked(monkeypatch):
    binding, unit = populated()
    saved = binding.snapshot_step(unit)
    original = binding.builder.dump
    monkeypatch.setattr(binding.builder, "dump", lambda unit: {"custom": original(unit)})
    assert "custom" in binding.snapshot_step(unit)["payload"]
    with pytest.raises(ValueError, match="codec/binding"):
        binding.restore_step(saved)


def test_step_snapshot_rejects_runtime_services_cycles_and_wrong_identity():
    binding, unit = populated()
    unit.notes["lock"] = threading.RLock()
    with pytest.raises(TypeError, match="runtime object"):
        binding.snapshot_step(unit)
    del unit.notes["lock"]
    unit.notes["cycle"] = unit.notes
    with pytest.raises(TypeError, match="cycle"):
        binding.snapshot_step(unit)
    del unit.notes["cycle"]
    saved = binding.snapshot_step(unit)
    saved["unit_id"] = "other"
    with pytest.raises(ValueError, match="identity"):
        binding.restore_step(saved)


def test_adapter_keeps_absent_unit_absent_and_checkpoint_portable():
    from tests.test_moead_plain_change import make
    solver, adapter = make()
    assert adapter.algorithm_unit is None
    absent = adapter.snapshot_step_state()
    assert absent["algorithm_unit"] is None
    adapter.restore_step_state(absent)
    assert adapter.algorithm_unit is None
    assert solver.step().committed
    step = adapter.snapshot_step_state()
    assert step["algorithm_unit"]["step_schema"].endswith("native-v1")
    assert "step_schema" not in adapter.get_state()["algorithm_unit"]
    json.dumps(adapter.get_state())


def test_native_capture_and_restore_do_not_call_persistent_codec(monkeypatch):
    binding, unit = populated()
    def forbidden(*args, **kwargs):
        pytest.fail("step rollback used the persistent codec")
    monkeypatch.setattr(UnitBinding, "dump", forbidden)
    monkeypatch.setattr(UnitBinding, "restore", forbidden)
    saved = binding.snapshot_step(unit)
    restored = binding.restore_step(saved)
    np.testing.assert_array_equal(restored.population, unit.population)


@pytest.mark.parametrize("value", [np.array([object()], dtype=object), threading.RLock(),
    np.array([1.], dtype=np.dtype("f8", metadata={"session": threading.RLock()}))])
def test_native_capture_rejects_unsupported_nested_data(value):
    binding, unit = populated()
    unit.notes["bad"] = value
    with pytest.raises(TypeError):
        binding.snapshot_step(unit)
