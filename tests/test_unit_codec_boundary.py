import json
import threading
import pytest
from nsgablack.representation import CandidateUnitBuilder, SearchNodeBuilder
from nsgablack.units import UnitBinding, UnitBuildRequest


def test_custom_codec_rejects_live_resources_and_detaches_data():
    class Builder(CandidateUnitBuilder):
        extra = {"items": [1]}
        def dump(self, unit):
            return {**super().dump(unit), "extra": self.extra}

    builder = Builder()
    binding = UnitBinding(builder)
    unit = binding.build(UnitBuildRequest("x", [1]))
    saved = binding.dump(unit)
    builder.extra["items"].append(2)
    assert saved["payload"]["extra"]["items"] == [1]
    builder.extra = {"session": threading.RLock()}
    with pytest.raises(TypeError, match="payload.extra.session"):
        binding.dump(unit)


def test_graph_parent_key_roundtrip_without_rebuilding():
    builder = SearchNodeBuilder()
    binding = UnitBinding(builder)
    unit = binding.build(UnitBuildRequest("child", [1], parameters={
        "g": 1, "h": 2, "f": 3, "parent_key": (b"parent", (1, 2)), "parent_id": "parent:1"}))
    saved = json.loads(json.dumps(binding.dump(unit)))
    builder.build = lambda *a, **k: pytest.fail("restore must not build")
    restored = binding.restore(saved)
    assert restored.unit_id == "child"
    assert restored.parent_key == (b"parent", (1, 2))
    assert restored.parent_id == "parent:1"
    saved["unit_id"] = "different"
    with pytest.raises(ValueError, match="identity"):
        binding.restore(saved)
