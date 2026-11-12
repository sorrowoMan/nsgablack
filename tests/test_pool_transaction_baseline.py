"""A step shares one Pool baseline without changing rejection or rollback."""
import copy

import pytest

from blackbase.contracts import BatchDisposition
from blackbase.runtime import RuntimeTransaction
from tests.test_solution_pool import batch, pool as make_pool
from tests.test_pool_search_adapter import make_solver


class RejectIntake:
    policy_id = "reject-shared-pool-baseline"

    def select(self, candidates, feedback, context):
        return BatchDisposition(len(candidates.semantic_states), ())


def watch_pool_capture(monkeypatch, pool):
    captures = []
    original = pool.snapshot_step_state

    def capture():
        state = original()
        captures.append((state, copy.deepcopy(state)))
        return state

    monkeypatch.setattr(pool, "snapshot_step_state", capture)
    return captures


@pytest.mark.parametrize("outcome", ["committed", "rejected", "failed"])
def test_one_pool_capture_preserves_step_outcomes_and_evaluation_cost(monkeypatch, outcome):
    solver, _, left, right = make_solver(count=2, batch_size=3)
    assert solver.step().committed
    assert solver.step().committed
    pool = solver.solution_pool
    before_refs, before_evaluations = pool.select(), solver.evaluation_count
    captures = watch_pool_capture(monkeypatch, pool)
    if outcome == "rejected":
        solver.set_evaluation_acceptance_policy(RejectIntake())
    elif outcome == "failed":
        original_update = right.update

        def fail_after_update(*args):
            original_update(*args)
            raise RuntimeError("second population failed")

        monkeypatch.setattr(right, "update", fail_after_update)

    if outcome == "failed":
        with pytest.raises(RuntimeError, match="second population failed"):
            solver.step()
    else:
        assert solver.step().status == outcome

    assert len(captures) == 1
    # In particular reject_attempt must not mutate the baseline later used by
    # rollback or commit cleanup, including its nested input/retention records.
    assert captures[0][0] == captures[0][1]
    assert solver.evaluation_count == before_evaluations + 4
    if outcome == "committed":
        assert len(left.population) == len(right.population) == 2
        assert all(pool.input_remaining(key) == 0 for key in solver.adapter.input_ids.values())
    else:
        assert pool.select() == before_refs
        assert left.population is None and right.population is None
        if outcome == "rejected":
            assert len(solver.adapter.input_ids) == 2
            assert all(pool.input_remaining(key) == 2 for key in solver.adapter.input_ids.values())
        else:
            assert solver.adapter.input_ids == {}


def test_error_after_pool_reconciliation_still_restores_original_baseline(monkeypatch):
    solver, _, left, right = make_solver(count=2, batch_size=3)
    assert solver.step().committed
    assert solver.step().committed
    pool = solver.solution_pool
    before_refs = pool.select()
    captures = watch_pool_capture(monkeypatch, pool)
    solver.set_evaluation_acceptance_policy(RejectIntake())
    original_reject = type(pool).reject_attempt
    reconciled = []

    def reject_then_fail(self, baseline):
        original_reject(self, baseline)
        reconciled.append(tuple(self._inputs))
        raise RuntimeError("failure after pool reconciliation")

    monkeypatch.setattr(type(pool), "reject_attempt", reject_then_fail)
    with pytest.raises(RuntimeError, match="failure after pool reconciliation"):
        solver.step()
    assert len(captures) == 1
    assert captures[0][0] == captures[0][1]
    assert len(reconciled) == 1 and len(reconciled[0]) == 2
    assert pool.select() == before_refs
    assert pool._inputs == {}
    assert solver.adapter.input_ids == {}
    assert left.population is None and right.population is None


def test_pool_reconciliation_preserves_nested_baseline_and_full_rollback(monkeypatch):
    pool = make_pool()
    refs = pool.put(batch(), stage="accepted")
    pool.create_subpool("baseline", refs, metadata={"notes": {"labels": ["a", "b"]}})
    existing_input = pool.bind_input(refs)
    captures = watch_pool_capture(monkeypatch, pool)
    transaction = RuntimeTransaction((pool,))
    pool.begin_attempt()
    pool.take_input(existing_input)
    created_input = pool.bind_input(refs[:1])
    pool.take_input(created_input)
    pool.create_subpool("new-selection", refs[:1], metadata={"notes": {"labels": ["c"]}})

    transaction.reconcile(pool, pool.reject_attempt)
    assert len(captures) == 1 and captures[0][0] == captures[0][1]
    assert pool.input_remaining(existing_input) == 2
    assert pool.input_remaining(created_input) == 1
    assert pool.subpool_descriptor("new-selection")
    # An error after reconciliation must still remove selections that did not
    # exist before the step, while retaining all original metadata and inputs.
    pool._subpool_metadata["baseline"]["notes"]["labels"].append("changed")
    transaction.rollback()
    assert captures[0][0] == captures[0][1]
    assert pool.input_remaining(existing_input) == 2
    assert created_input not in pool._inputs
    assert "new-selection" not in pool._subpool_metadata
    assert pool._subpool_metadata["baseline"]["notes"] == {"labels": ["a", "b"]}
