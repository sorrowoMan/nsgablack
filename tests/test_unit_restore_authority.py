"""Codec Unit 与依赖版本在兼容字段恢复之后仍然是同一权威事实。"""
import copy

import numpy as np
import pytest

from nsgablack.adapters.gaussian_search import GaussianSearchAdapter


class NativeGaussian(GaussianSearchAdapter):
    def _snapshot_algorithm_step_state(self):
        return self._get_algorithm_state()

    def _restore_algorithm_step_state(self, state):
        self._set_algorithm_state(state)


@pytest.mark.parametrize("native", [False, True])
def test_compatibility_fields_cannot_overwrite_codec_candidate_metadata_or_score(native, monkeypatch):
    adapter = NativeGaussian() if native else GaussianSearchAdapter()
    adapter.best_x = np.asarray([2.])
    adapter._candidate_metadata = {"tag": "authoritative"}
    adapter.best_score = 4.
    saved = copy.deepcopy(adapter.snapshot_step_state() if native else adapter.get_state())
    saved.update(best_x=[99.], best_score=999., candidate_metadata={"tag": "compatibility"})
    monkeypatch.setattr(adapter.unit_binding.builder, "build",
                        lambda *a, **k: pytest.fail("restore must not invoke a Unit builder"))
    (adapter.restore_step_state if native else adapter.set_state)(saved)
    np.testing.assert_array_equal(adapter.best_x, [2.])
    assert adapter._candidate_metadata == {"tag": "authoritative"}
    assert adapter.best_score == 4.


@pytest.mark.parametrize("native", [False, True])
def test_changed_codec_candidate_does_not_heal_or_rebind_its_stale_feedback(native):
    adapter = NativeGaussian() if native else GaussianSearchAdapter()
    adapter.best_x = np.asarray([2.])
    adapter.best_score = 4.
    saved = copy.deepcopy(adapter.snapshot_step_state() if native else adapter.get_state())
    binding = adapter.unit_binding
    unit = (binding.restore_step if native else binding.restore)(saved["algorithm_unit"])
    unit.best = np.asarray([9.])
    saved["algorithm_unit"] = (binding.snapshot_step if native else binding.dump)(unit)
    (adapter.restore_step_state if native else adapter.set_state)(saved)
    np.testing.assert_array_equal(adapter.best_x, [9.])
    assert adapter.best_score is None
