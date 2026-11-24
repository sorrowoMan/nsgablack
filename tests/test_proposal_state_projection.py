from types import SimpleNamespace
import numpy as np
import pytest
from blackbase.contracts import BatchDisposition
from nsgablack.adapters import DifferentialEvolutionAdapter, MOEADAdapter
from nsgablack.adapters.proposal_state import project_pending_proposals


def disposition():
    return BatchDisposition(proposed_count=3, accepted_indices=(1, 2), reason="test")


def test_pending_projection_validates_all_columns_before_changing_unit():
    unit = SimpleNamespace(indices=[4, 5, 6], scores=np.array([1., 2., 3.]))
    adapter = SimpleNamespace(algorithm_unit=unit, admission_unit_fields=("indices", "scores"),
                              proposal_column_fields=("baseline",), baseline={"x": np.ones((2, 1))})
    with pytest.raises(ValueError, match="align"):
        project_pending_proposals(adapter, disposition())
    assert unit.indices == [4, 5, 6]
    np.testing.assert_array_equal(unit.scores, [1., 2., 3.])
    adapter.baseline = {"x": np.arange(3).reshape(-1, 1)}
    project_pending_proposals(adapter, disposition())
    assert unit.indices == [5, 6]
    np.testing.assert_array_equal(unit.scores, [2., 3.])
    np.testing.assert_array_equal(adapter.baseline["x"], [[1], [2]])


@pytest.mark.parametrize("kind", ["de", "moead"])
def test_native_disposition_uses_same_projection_for_nonprefix_admission(kind):
    if kind == "de":
        adapter = DifferentialEvolutionAdapter()
        adapter._last_target_indices = [4, 5, 6]
        adapter._last_target_scores = np.array([1., 2., 3.])
        adapter._last_target_baselines = {"x": np.arange(3).reshape(-1, 1)}
    else:
        adapter = MOEADAdapter()
        adapter._pending_indices = [4, 5, 6]
        adapter._pending_modes = ["a", "b", "c"]
    adapter.on_proposal_disposition(None, disposition(), {})
    if kind == "de":
        assert adapter._last_target_indices == [5, 6]
        np.testing.assert_array_equal(adapter._last_target_baselines["x"], [[1], [2]])
    else:
        assert adapter._pending_indices == [5, 6]
        assert adapter._pending_modes == ["b", "c"]
    with pytest.raises(ValueError, match="pending"):
        adapter.on_proposal_disposition(None, disposition(), {})
