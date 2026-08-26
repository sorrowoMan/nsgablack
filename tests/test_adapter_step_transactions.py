from __future__ import annotations

import numpy as np
import pytest

from blackbase.context import InMemorySnapshotStore
from blackbase.evaluation import InMemoryEvaluationEvidenceJournal
from blackbase.evaluation import StateReleaseResult
from blackbase.resources import ResourceContext
from blackbase.state_ref import StateRef
from nsgablack.adapters import (
    AdapterCommitReport,
    AdapterRollbackError,
    AdapterStepTransaction,
)
from nsgablack.adapters.algorithm_adapter import (
    AlgorithmAdapter,
    CompositeAdapter,
)
from nsgablack.adapters.differential_evolution import DifferentialEvolutionAdapter
from nsgablack.adapters.gradient_optimizer import GradientOptimizerAdapter
from nsgablack.adapters.moead import MOEADAdapter
from nsgablack.adapters.nsga2 import NSGA2Adapter
from nsgablack.core.base import BlackBoxProblem
from nsgablack.core.composable_solver import ComposableSolver


def test_step_transaction_protocol_is_public() -> None:
    assert AdapterStepTransaction.__name__ == "AdapterStepTransaction"
    assert AdapterRollbackError.__name__ == "AdapterRollbackError"


class _StateAdapter(AlgorithmAdapter):
    def __init__(
        self,
        name: str,
        *,
        fail_restore: bool = False,
        fail_commit: bool = False,
    ) -> None:
        super().__init__(name=name)
        self.value = 1
        self.fail_restore = fail_restore
        self.fail_commit = fail_commit
        self.restore_calls = 0
        self.commit_calls = 0

    def propose(self, control, context):
        del control, context
        return ()

    def update(self, control, candidates, feedback, context):
        del control, candidates, feedback, context

    def get_state(self):
        return {"value": self.value}

    def set_state(self, state):
        self.restore_calls += 1
        if self.fail_restore:
            raise RuntimeError(f"restore failed: {self.name}")
        self.value = int(state["value"])

    def commit_step_state(self, state):
        del state
        self.commit_calls += 1
        if self.fail_commit:
            raise RuntimeError(f"commit failed: {self.name}")


def test_composite_transaction_restores_each_child_exactly_once() -> None:
    first = _StateAdapter("first")
    second = _StateAdapter("second")
    root = CompositeAdapter([first, second])

    transaction = root.begin_step_transaction()
    first.value = 7
    second.value = 8
    transaction.rollback()

    assert first.value == 1
    assert second.value == 1
    assert first.restore_calls == 1
    assert second.restore_calls == 1


def test_adapter_rollback_attempts_every_participant_before_raising() -> None:
    first = _StateAdapter("first", fail_restore=True)
    middle = _StateAdapter("middle")
    last = _StateAdapter("last", fail_restore=True)
    transaction = CompositeAdapter([first, middle, last]).begin_step_transaction()

    with pytest.raises(AdapterRollbackError) as caught:
        transaction.rollback()

    assert middle.restore_calls == 1
    assert first.restore_calls == 1
    assert last.restore_calls == 1
    assert len(caught.value.errors) == 2


def test_adapter_commit_reports_cleanup_failures_after_attempting_every_participant() -> None:
    first = _StateAdapter("first", fail_commit=True)
    middle = _StateAdapter("middle")
    last = _StateAdapter("last", fail_commit=True)

    report = CompositeAdapter([first, middle, last]).begin_step_transaction().commit()

    assert isinstance(report, AdapterCommitReport)
    assert report.cleanup_complete is False
    assert len(report.issues) == 2
    assert first.commit_calls == middle.commit_calls == last.commit_calls == 1


@pytest.mark.parametrize(
    "adapter",
    [DifferentialEvolutionAdapter(), NSGA2Adapter()],
)
def test_random_adapter_transaction_restores_exact_rng_position(adapter) -> None:
    adapter._rng = np.random.default_rng(123)
    expected = np.random.default_rng(123).random()
    transaction = adapter.begin_step_transaction()

    adapter._rng.random()
    if isinstance(adapter, DifferentialEvolutionAdapter):
        adapter._last_target_indices = [4]
        adapter._last_target_scores = np.asarray([5.0])
    transaction.rollback()

    assert adapter._rng.random() == expected
    if isinstance(adapter, DifferentialEvolutionAdapter):
        assert adapter._last_target_indices == []
        assert adapter._last_target_scores.size == 0


def test_moead_transaction_restores_population_pending_and_rng() -> None:
    adapter = MOEADAdapter()
    adapter._n = 2
    adapter._m = 1
    adapter.pop_X = np.asarray([[1.0], [2.0]])
    adapter.pop_F = np.asarray([[1.0], [4.0]])
    adapter.pop_V = np.asarray([0.0, 0.0])
    adapter._population_candidate_tokens = ("a", "b")
    adapter._pending_indices = [1]
    adapter._pending_modes = ["global"]
    adapter._rng = np.random.default_rng(9)
    expected = np.random.default_rng(9).random()
    transaction = adapter.begin_step_transaction()

    adapter.pop_X[0, 0] = 99.0
    adapter._pending_indices = [0]
    adapter._pending_modes = ["neighborhood"]
    adapter._rng.random()
    transaction.rollback()

    assert adapter.pop_X.tolist() == [[1.0], [2.0]]
    assert adapter._pending_indices == [1]
    assert adapter._pending_modes == ["global"]
    assert adapter._population_candidate_tokens == ("a", "b")
    assert adapter._rng.random() == expected


class _Gateway:
    def __init__(self) -> None:
        self.releases = []

    def release(self, request, resource):
        self.releases.append((request, resource))
        return StateReleaseResult(
            request_id=request.request_id,
            provider_id=request.provider_id,
            status="released",
            released_count=len(request.state_ids),
            released_state_ids=tuple(request.state_ids),
        )


def test_gradient_transaction_does_not_materialize_and_releases_aborted_slots() -> None:
    gateway = _Gateway()
    resource = ResourceContext(namespace="case.fit", grant={"threads": 1})
    adapter = GradientOptimizerAdapter(state_gateway=gateway)
    old_m = StateRef(
        provider_id="provider/v1",
        state_id="slot-m",
        state_kind="optimizer_slot.m",
        scope_id="case.fit",
        trajectory_id="fit-1",
    )
    old_v = StateRef(
        provider_id="provider/v1",
        state_id="slot-v",
        state_kind="optimizer_slot.v",
        scope_id="case.fit",
        trajectory_id="fit-1",
    )
    adapter.current_x = np.asarray([1.0])
    adapter._first_moment = np.asarray([0.1])
    adapter._second_moment = np.asarray([0.2])
    adapter._provider_slot_refs = {"m": old_m, "v": old_v}
    adapter._provider_resource_context = resource
    transaction = adapter.begin_step_transaction()

    adapter._first_moment[:] = 7.0
    adapter._second_moment[:] = 8.0
    new_m = StateRef(
        provider_id="provider/v1",
        state_id="slot-m-next",
        state_kind="optimizer_slot.m",
        scope_id="case.fit",
        trajectory_id="fit-1",
        version=1,
    )
    new_v = StateRef(
        provider_id="provider/v1",
        state_id="slot-v-next",
        state_kind="optimizer_slot.v",
        scope_id="case.fit",
        trajectory_id="fit-1",
        version=1,
    )
    adapter._step_transaction_slot_refs = {
        "m": new_m,
        "v": new_v,
    }
    adapter._step_transaction_resource_context = resource
    transaction.rollback()

    assert len(gateway.releases) == 1
    request, released_resource = gateway.releases[0]
    assert request.state_ids == ("slot-m-next", "slot-v-next")
    assert released_resource is resource
    assert adapter._provider_slot_refs == {"m": old_m, "v": old_v}
    assert adapter._provider_transition_needs_slot_seed is False
    assert adapter._first_moment.tolist() == [0.1]
    assert adapter._second_moment.tolist() == [0.2]


def test_gradient_transaction_commit_retires_only_predecessor_slots() -> None:
    gateway = _Gateway()
    resource = ResourceContext(namespace="case.fit", grant={"threads": 1})
    adapter = GradientOptimizerAdapter(state_gateway=gateway)
    old_m = StateRef(
        provider_id="provider/v1",
        state_id="slot-m-old",
        state_kind="optimizer_slot.m",
        scope_id="case.fit",
        trajectory_id="fit-1",
    )
    old_v = StateRef(
        provider_id="provider/v1",
        state_id="slot-v-old",
        state_kind="optimizer_slot.v",
        scope_id="case.fit",
        trajectory_id="fit-1",
    )
    adapter.current_x = np.asarray([1.0])
    adapter._provider_slot_refs = {"m": old_m, "v": old_v}
    adapter._provider_resource_context = resource
    transaction = adapter.begin_step_transaction()
    adapter._step_transaction_slot_refs = {
        "m": StateRef(
            provider_id="provider/v1",
            state_id="slot-m-next",
            state_kind="optimizer_slot.m",
            scope_id="case.fit",
            trajectory_id="fit-1",
        ),
        "v": StateRef(
            provider_id="provider/v1",
            state_id="slot-v-next",
            state_kind="optimizer_slot.v",
            scope_id="case.fit",
            trajectory_id="fit-1",
        ),
    }
    adapter._step_transaction_resource_context = resource

    report = transaction.commit()

    assert len(gateway.releases) == 1
    request, released_resource = gateway.releases[0]
    assert request.state_ids == ("slot-m-old", "slot-v-old")
    assert released_resource is resource
    assert adapter._step_transaction_slot_refs == {}
    release_evidence = report.evidence[0].payload["provider_releases"][0]
    assert release_evidence["released_state_ids"] == ["slot-m-old", "slot-v-old"]
    assert release_evidence["not_found_state_ids"] == []


class _FailingReleaseGateway(_Gateway):
    def release(self, request, resource):
        self.releases.append((request, resource))
        raise RuntimeError("release unavailable")


class _NotFoundReleaseGateway(_Gateway):
    def release(self, request, resource):
        self.releases.append((request, resource))
        return StateReleaseResult(
            request_id=request.request_id,
            provider_id=request.provider_id,
            status="not_found",
            released_count=0,
            not_found_state_ids=tuple(request.state_ids),
        )


class _IncompleteReleaseGateway(_Gateway):
    def release(self, request, resource):
        self.releases.append((request, resource))
        return StateReleaseResult(
            request_id=request.request_id,
            provider_id=request.provider_id,
            status="not_found",
            released_count=0,
        )


def test_gradient_commit_cleanup_failure_is_retryable_and_does_not_poison_next_step() -> None:
    gateway = _FailingReleaseGateway()
    resource = ResourceContext(namespace="case.fit", grant={"threads": 1})
    adapter = GradientOptimizerAdapter(state_gateway=gateway)
    predecessor = StateRef(
        provider_id="provider/v1",
        state_id="slot-old",
        state_kind="optimizer_slot.m",
        scope_id="case.fit",
        trajectory_id="fit-1",
    )
    adapter._provider_slot_refs = {"m": predecessor}
    adapter._provider_resource_context = resource
    transaction = adapter.begin_step_transaction()
    adapter._step_transaction_slot_refs = {
        "m": StateRef(
            provider_id="provider/v1",
            state_id="slot-next",
            state_kind="optimizer_slot.m",
            scope_id="case.fit",
            trajectory_id="fit-1",
        )
    }
    adapter._step_transaction_resource_context = resource

    report = transaction.commit()

    assert report.cleanup_complete is False
    assert adapter._step_transaction_slot_refs == {}
    assert set(adapter._provider_cleanup_refs) == {"slot-old"}
    retry = adapter.begin_step_transaction()
    retry.rollback()


@pytest.mark.parametrize(
    ("gateway", "cleanup_complete", "not_found_ids"),
    [
        (_NotFoundReleaseGateway(), True, ["slot-old"]),
        (_IncompleteReleaseGateway(), False, None),
    ],
)
def test_gradient_release_requires_exact_state_id_evidence(
    gateway,
    cleanup_complete,
    not_found_ids,
) -> None:
    resource = ResourceContext(namespace="case.fit", grant={"threads": 1})
    adapter = GradientOptimizerAdapter(state_gateway=gateway)
    predecessor = StateRef(
        provider_id="provider/v1",
        state_id="slot-old",
        state_kind="optimizer_slot.m",
        scope_id="case.fit",
        trajectory_id="fit-1",
    )
    adapter._provider_slot_refs = {"m": predecessor}
    adapter._provider_resource_context = resource
    transaction = adapter.begin_step_transaction()
    adapter._step_transaction_slot_refs = {
        "m": StateRef(
            provider_id="provider/v1",
            state_id="slot-next",
            state_kind="optimizer_slot.m",
            scope_id="case.fit",
            trajectory_id="fit-1",
        )
    }
    adapter._step_transaction_resource_context = resource

    report = transaction.commit()

    assert report.cleanup_complete is cleanup_complete
    if cleanup_complete:
        assert adapter._provider_cleanup_refs == {}
        release = report.evidence[0].payload["provider_releases"][0]
        assert release["not_found_state_ids"] == not_found_ids
    else:
        assert report.evidence == ()
        assert set(adapter._provider_cleanup_refs) == {"slot-old"}


def test_gradient_checkpoint_preserves_only_portable_provider_cleanup_debt() -> None:
    adapter = GradientOptimizerAdapter()
    host_ref = StateRef(
        provider_id="provider/v1",
        state_id="host-slot",
        state_kind="optimizer_slot.m",
        scope_id="case.fit",
        trajectory_id="fit-1",
        transport_scope="host",
    )
    process_ref = StateRef(
        provider_id="provider/v1",
        state_id="process-slot",
        state_kind="optimizer_slot.v",
        scope_id="case.fit",
        trajectory_id="fit-1",
        transport_scope="process",
    )
    adapter._provider_cleanup_refs = {
        host_ref.state_id: host_ref,
        process_ref.state_id: process_ref,
    }

    state = adapter.get_state()
    cleanup = state["provider_transition"]["cleanup_refs"]
    assert set(cleanup) == {"host-slot"}
    assert state["provider_transition"]["nonportable_cleanup_ref_count"] == 1

    restored = GradientOptimizerAdapter()
    restored.set_state(state)
    assert restored._provider_cleanup_refs == {"host-slot": host_ref}


def test_restored_gradient_cleanup_debt_is_released_with_control_grant() -> None:
    gateway = _Gateway()
    resource = ResourceContext(namespace="case.fit", grant={"threads": 1})
    ref = StateRef(
        provider_id="provider/v1",
        state_id="host-slot",
        state_kind="optimizer_slot.m",
        scope_id="case.fit",
        trajectory_id="fit-1",
        transport_scope="host",
    )
    source = GradientOptimizerAdapter()
    source._provider_cleanup_refs = {ref.state_id: ref}
    restored = GradientOptimizerAdapter(state_gateway=gateway)
    restored.set_state(source.get_state())

    class _Control:
        def get_resource_context(self):
            return resource

    restored.teardown(_Control())

    assert len(gateway.releases) == 1
    request, released_resource = gateway.releases[0]
    assert request.state_ids == ("host-slot",)
    assert released_resource is resource
    assert restored._provider_cleanup_refs == {}


class _OneCandidateAdapter(AlgorithmAdapter):
    def __init__(self) -> None:
        super().__init__(name="one-candidate")

    def propose(self, control, context):
        del control, context
        return (np.asarray([0.5]),)

    def update(self, control, candidates, feedback, context):
        del control, candidates, feedback, context


class _FailAfterSnapshotSolver(ComposableSolver):
    def _update_best(self, *args, **kwargs):
        del args, kwargs
        raise RuntimeError("incumbent publication failed")


def test_failed_step_never_overwrites_the_last_committed_snapshot() -> None:
    solver = _FailAfterSnapshotSolver(_Problem(), adapter=_OneCandidateAdapter())
    assert solver.write_population_snapshot(
        np.asarray([[0.9]]),
        np.asarray([[0.81]]),
        np.asarray([0.0]),
    )
    committed_handle = solver._latest_snapshot_handle
    assert committed_handle is not None

    with pytest.raises(RuntimeError, match="incumbent publication failed"):
        solver.step()

    assert solver._latest_snapshot_handle == committed_handle
    committed = solver.read_snapshot(committed_handle.key)
    assert committed is not None
    assert np.asarray(committed["population"]).tolist() == [[0.9]]


def test_successful_adapter_cleanup_report_is_durable_and_referenced() -> None:
    from blackbase.context.context_keys import KEY_ADAPTER_COMMIT_REPORT_REF

    solver = ComposableSolver(_Problem(), adapter=_OneCandidateAdapter())

    outcome = solver.step()

    report = outcome.metadata["adapter_post_commit_cleanup"]
    report_key = outcome.metadata["adapter_commit_report_snapshot_key"]
    record = solver.snapshot_store.read(report_key)
    assert report["cleanup_complete"] is True
    assert record is not None
    assert record.schema == "nsgablack.adapter_commit_report/v2"
    stored = record.data["adapter_commit_report"]
    assert stored["schema"] == report["schema"]
    assert stored["cleanup_complete"] is True
    assert stored["participants"] == list(report["participants"])
    assert stored["issues"] == list(report["issues"])
    assert stored["evidence"] == list(report["evidence"])
    assert solver.context_store.get(KEY_ADAPTER_COMMIT_REPORT_REF) == report_key


class _FailingSnapshotStore(InMemorySnapshotStore):
    def __init__(self) -> None:
        super().__init__()
        self.write_count = 0
        self.fail_on_write: int | None = None

    def write(self, *args, **kwargs):
        self.write_count += 1
        if self.fail_on_write == self.write_count:
            raise RuntimeError("snapshot backend unavailable")
        return super().write(*args, **kwargs)


def test_authority_rolls_back_when_staged_snapshot_cannot_publish() -> None:
    store = _FailingSnapshotStore()
    solver = ComposableSolver(_Problem(), adapter=_OneCandidateAdapter())
    solver.set_snapshot_store(
        store,
        evaluation_evidence_journal=InMemoryEvaluationEvidenceJournal(),
    )
    assert solver.write_population_snapshot(
        np.asarray([[0.9]]),
        np.asarray([[0.81]]),
        np.asarray([0.0]),
    )
    committed_handle = solver._latest_snapshot_handle
    # One evaluation-event write succeeds; the following authority promotion
    # is the write that must fail and roll the in-memory step back.
    store.fail_on_write = store.write_count + 2

    with pytest.raises(RuntimeError, match="snapshot backend unavailable"):
        solver.step()

    assert solver._latest_snapshot_handle == committed_handle
    assert np.asarray(solver.population).tolist() == [[0.9]]


class _Problem(BlackBoxProblem):
    def __init__(self) -> None:
        super().__init__(dimension=1, bounds=[(-1.0, 1.0)], objectives=["min"])

    def evaluate(self, candidate):
        return float(np.asarray(candidate, dtype=float).reshape(-1)[0] ** 2)


class _PrimaryFailureAdapter(_StateAdapter):
    def propose(self, control, context):
        del context
        control.population = np.asarray([[99.0]])
        raise ValueError("primary propose failure")


def test_solver_preserves_primary_error_when_adapter_rollback_also_fails() -> None:
    adapter = _PrimaryFailureAdapter("broken", fail_restore=True)
    solver = ComposableSolver(_Problem(), adapter=adapter)
    solver.population = np.asarray([[1.0]])
    solver.objectives = np.asarray([[1.0]])
    solver.constraint_violations = np.asarray([0.0])

    with pytest.raises(ValueError, match="primary propose failure") as caught:
        solver.step()

    assert solver.population.tolist() == [[1.0]]
    evidence = caught.value.step_rollback_errors
    assert evidence[0]["participant"] == "adapter"
