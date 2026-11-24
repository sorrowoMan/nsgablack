import numpy as np
import pytest

from blackbase.runtime import RuntimeTransaction
from nsgablack.adapters import AlgorithmAdapter
from nsgablack.core import BlackBoxProblem, ComposableSolver


class CountingAdapter(AlgorithmAdapter):
    def __init__(self, *, fail=False):
        super().__init__(name="counting")
        self.value = 0
        self.captures = self.restores = self.cleanups = 0
        self.fail = fail

    def snapshot_step_state(self):
        self.captures += 1
        return {"value": self.value}

    def restore_step_state(self, state):
        self.restores += 1
        self.value = state["value"]

    def commit_step_state(self, state):
        self.cleanups += 1

    def propose(self, control, context):
        self.captures_at_propose = self.captures
        return [np.array([0.5])]

    def update(self, control, candidates, feedback, context):
        self.value += 1
        if self.fail:
            raise RuntimeError("update failed")


class Sphere(BlackBoxProblem):
    def __init__(self):
        super().__init__(dimension=1, objectives=["minimize"], bounds=[(-1, 1)])

    def evaluate(self, x):
        return [float(x[0] ** 2)]


@pytest.mark.parametrize("fail", [False, True])
def test_shared_solver_adapter_owner_is_captured_and_finished_once(fail):
    adapter = CountingAdapter(fail=fail)
    solver = ComposableSolver(Sphere(), adapter=adapter)
    solver.register_state_participant(adapter)
    if fail:
        with pytest.raises(RuntimeError, match="update failed"):
            solver.step()
        assert adapter.value == 0
        assert adapter.restores == 1
        assert adapter.cleanups == 0
        assert solver.evaluation_count == 1
    else:
        assert solver.step().committed
        assert adapter.value == 1
        assert adapter.cleanups == 1
    assert adapter.captures_at_propose == 1


def test_partition_transfers_capture_and_rejects_duplicate_transfer():
    owner = CountingAdapter()
    transaction = RuntimeTransaction([owner, owner])
    child = transaction.partition([owner])
    assert owner.captures == 1
    with pytest.raises(ValueError, match="already transferred"):
        transaction.partition([owner])
    owner.value = 9
    transaction.reconcile(owner, owner.restore_step_state)
    assert owner.value == 0
    child.commit()
    with pytest.raises(RuntimeError, match="no longer active"):
        transaction.reconcile(owner, owner.restore_step_state)
    transaction.commit()
    assert owner.cleanups == 1


def test_partition_validation_does_not_consume_other_captures():
    owner, unknown = CountingAdapter(), CountingAdapter()
    transaction = RuntimeTransaction([owner])
    with pytest.raises(ValueError, match="uncaptured"):
        transaction.partition([owner, unknown])
    owner.value = 9
    transaction.rollback()
    assert owner.restores == 1
    assert unknown.captures == unknown.restores == 0


def test_zero_admission_hook_observes_previous_authority_projection():
    from blackbase.contracts import BatchDisposition
    class RejectAll:
        name = "reject-all"
        def select(self, batch, feedback, context):
            return BatchDisposition(proposed_count=len(batch.candidate_tokens),
                                    accepted_indices=(), reason="test")
    class Observer(CountingAdapter):
        def on_proposal_disposition(self, control, disposition, context):
            if not disposition.accepted_indices:
                self.observed = np.array(control.population, copy=True)
    adapter = Observer()
    solver = ComposableSolver(Sphere(), adapter=adapter)
    assert solver.step().committed
    previous = np.array(solver.population, copy=True)
    adapter.propose = lambda control, context: [np.array([0.75])]
    solver.evaluation_acceptance_policy = RejectAll()
    assert solver.step().status == "rejected"
    np.testing.assert_array_equal(adapter.observed, previous)
    assert solver.evaluation_count == 2
