"""Failures after real MOEA/D variation must not undo consumed work."""
import copy
import numpy as np
import pytest
from blackbase.resources import CancellationRequested
from tests.test_moead_plain_change import make
from tests.test_shared_evaluation_budget import _runtime


@pytest.mark.parametrize("failure", [RuntimeError, CancellationRequested])
def test_steady_update_failure_restores_members_but_keeps_durable_consumption(tmp_path, monkeypatch, failure):
    runtime = _runtime(tmp_path, limit=20)
    lease = runtime.acquire_case("steady", stage_name="test")
    solver, adapter = make()
    solver.set_resource_context(runtime.resource_context(lease, case_name="steady"))
    assert solver.step().committed  # Real population bootstrap.
    assert solver.step().committed  # Real custom variation and replacement.
    before = copy.deepcopy(adapter.get_state())
    refs = adapter.get_population_solution_refs(solver)
    authority = solver.get_population_authority_identity()
    consumed = runtime.budget_authority.status("evaluations").committed
    evaluations = solver.evaluation_count
    original = adapter.update

    def fail_after_update(*args, **kwargs):
        original(*args, **kwargs)
        raise failure("injected after steady update")

    with monkeypatch.context() as patch:
        patch.setattr(adapter, "update", fail_after_update)
        with pytest.raises(failure, match="injected after steady update"):
            solver.step()
    assert adapter.get_state() == before
    assert adapter.get_population_solution_refs(solver) == refs
    assert solver.get_population_authority_identity() == authority
    status = runtime.budget_authority.status("evaluations")
    assert status.committed == consumed + 2
    assert solver.evaluation_count == evaluations + 2
    assert status.reserved == 0
    assert solver.step().committed
    runtime.release(lease)


def test_unit_codec_roundtrip_after_steady_replacement():
    solver, adapter = make()
    for _ in range(3):
        assert solver.step().committed
    state = copy.deepcopy(adapter.get_state())
    _, restored = make()
    restored.set_state(state)
    assert restored.get_state() == state
    np.testing.assert_array_equal(restored.pop_X, adapter.pop_X)
    np.testing.assert_array_equal(restored.pop_F, adapter.pop_F)
