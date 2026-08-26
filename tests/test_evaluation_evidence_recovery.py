from __future__ import annotations

import numpy as np
import pytest

from blackbase import CandidateBatch, UnknownState
from blackbase.context import InMemorySnapshotStore
from blackbase.evaluation import (
    EvaluationDispositionEnvelope,
    EvaluationEventEnvelope,
    InMemoryEvaluationEvidenceJournal,
)
from nsgablack.adapters import AlgorithmAdapter
from nsgablack.core import BlackBoxProblem, ComposableSolver
from nsgablack.core.state.incumbent import CandidateProvenance


class _Problem(BlackBoxProblem):
    def __init__(self) -> None:
        super().__init__(dimension=1, objectives=["minimize"], bounds=[(-1.0, 1.0)])

    def evaluate(self, candidate):
        return float(np.asarray(candidate, dtype=float)[0] ** 2)


class _Adapter(AlgorithmAdapter):
    def __init__(self) -> None:
        super().__init__(name="recovery-test")
        self.update_calls = 0

    def propose(self, control, context):
        del control, context
        return [[0.5]]

    def update(self, control, candidates, feedback, context):
        del control, candidates, feedback, context
        self.update_calls += 1


def _event(event_id: str, run_id: str, snapshot_key: str) -> EvaluationEventEnvelope:
    return EvaluationEventEnvelope(
        event_id=event_id,
        candidate_codec="test.candidate/v1",
        candidate_payload={"rows": [[0.5]]},
        feedback_codec="test.feedback/v1",
        feedback_payload={"objectives": [[0.25]]},
        identity={"run_id": run_id, "event_snapshot_key": snapshot_key},
        evaluation_count=1,
    )


def _write_event_snapshot(solver, event: EvaluationEventEnvelope, key: str) -> None:
    solver.snapshot_store.write(
        {
            "last_evaluation_event": {
                "evaluation_event_envelope": event.as_dict(),
            }
        },
        key=key,
        schema="nsgablack.population_snapshot/v2",
    )


def _authority_payload(
    disposition: EvaluationDispositionEnvelope,
) -> dict[str, object]:
    token = "candidate:test:0"
    state = UnknownState(values=np.asarray([0.5]), metadata={"kind": "test"})
    batch = CandidateBatch(
        semantic_states=(state,),
        numeric_matrix=np.asarray([[0.5]]),
        candidate_tokens=(token,),
    )
    return {
        "population": np.asarray([[0.5]]),
        "objectives": np.asarray([[0.25]]),
        "constraint_violations": np.asarray([0.0]),
        "population_authority": {
            "schema": "nsgablack.population_snapshot/v2",
            "authority_mode": "step_batch",
        },
        "candidate_batch": batch.as_dict(),
        "candidate_provenance": [
            CandidateProvenance(
                candidate_token=token,
                source_run_id="run-recovery",
            ).as_dict()
        ],
        "last_evaluation_disposition": disposition.as_dict(),
    }


def test_recovery_archives_pending_event_without_replaying_policy_or_adapter() -> None:
    adapter = _Adapter()
    solver = ComposableSolver(_Problem(), adapter=adapter)
    solver._active_run_id = "run-recovery"
    event_id = "event-pending"
    event_key = "evaluation-evidence/event/event-pending"
    event = _event(event_id, solver._active_run_id, event_key)
    _write_event_snapshot(solver, event, event_key)
    solver.evaluation_evidence_journal.reserve(
        event_id=event_id,
        run_id=solver._active_run_id,
        event_snapshot_key=event_key,
        identity=event.identity,
    )
    solver.evaluation_evidence_journal.mark_event_durable(event_id)

    report = solver.reconcile_evaluation_evidence()

    record = solver.evaluation_evidence_journal.get(event_id)
    assert record is not None
    assert record.status == "abandoned"
    assert record.metadata["abandon_reason"] == "decision_not_durable"
    assert report["abandoned_count"] == 1
    assert adapter.update_calls == 0
    assert solver.evaluation_count == 0


def test_recovery_settles_committed_authority_after_process_crash_window() -> None:
    solver = ComposableSolver(_Problem(), adapter=_Adapter())
    solver._active_run_id = "run-recovery"
    event_id = "event-committed"
    event_key = "evaluation-evidence/event/event-committed"
    authority_key = "authority/event-committed"
    event = _event(event_id, solver._active_run_id, event_key)
    _write_event_snapshot(solver, event, event_key)
    journal = solver.evaluation_evidence_journal
    journal.reserve(
        event_id=event_id,
        run_id=solver._active_run_id,
        event_snapshot_key=event_key,
        identity=event.identity,
    )
    journal.mark_event_durable(event_id)
    disposition = EvaluationDispositionEnvelope(
        event_id=event_id,
        status="committed",
        disposition_codec="nsgablack.evaluation_disposition/v1",
        disposition_payload={"step_status": "committed"},
        event_snapshot_key=event_key,
        authority_snapshot_key=authority_key,
        identity=event.identity,
        metadata={"authority_mode": "step_batch"},
    )
    deciding = journal.prepare_disposition(disposition)
    solver.snapshot_store.write(
        _authority_payload(disposition),
        key=authority_key,
        schema="nsgablack.population_snapshot/v2",
    )

    report = solver.reconcile_evaluation_evidence()

    recovered = journal.get(event_id)
    assert recovered is not None
    assert deciding.status == "deciding"
    assert recovered.status == "committed"
    assert recovered.terminal_verified
    assert report["settled_count"] == 1
    assert report["abandoned_count"] == 0


def test_recovery_keeps_semantically_invalid_authority_retryable() -> None:
    solver = ComposableSolver(_Problem(), adapter=_Adapter())
    solver._active_run_id = "run-recovery"
    event_id = "event-invalid-authority"
    event_key = "evaluation-evidence/event/event-invalid-authority"
    authority_key = "authority/event-invalid-authority"
    event = _event(event_id, solver._active_run_id, event_key)
    _write_event_snapshot(solver, event, event_key)
    journal = solver.evaluation_evidence_journal
    journal.reserve(
        event_id=event_id,
        run_id=solver._active_run_id,
        event_snapshot_key=event_key,
        identity=event.identity,
    )
    journal.mark_event_durable(event_id)
    disposition = EvaluationDispositionEnvelope(
        event_id=event_id,
        status="committed",
        disposition_codec="nsgablack.evaluation_disposition/v1",
        disposition_payload={"step_status": "committed"},
        event_snapshot_key=event_key,
        authority_snapshot_key=authority_key,
        identity=event.identity,
        metadata={"authority_mode": "single"},
    )
    journal.prepare_disposition(disposition)
    solver.snapshot_store.write(
        {
            "population_authority": {
                "schema": "nsgablack.population_snapshot/v2",
                "authority_mode": "single",
            },
            "population": np.asarray([[0.5], [0.75]]),
            "objectives": np.asarray([[0.25]]),
            "constraint_violations": np.asarray([0.0]),
            "last_evaluation_disposition": disposition.as_dict(),
        },
        key=authority_key,
        schema="nsgablack.population_snapshot/v2",
    )

    report = solver.reconcile_evaluation_evidence()

    recovered = journal.get(event_id)
    assert recovered is not None
    assert recovered.status == "deciding"
    assert not recovered.terminal_verified
    assert report["status"] == "deferred"
    assert report["deferred_count"] == 1
    assert report["abandoned_count"] == 0
    assert report["records"][0]["reason"] == (
        "authority_snapshot_semantically_invalid"
    )


def test_normal_step_closes_journal_to_same_committed_disposition() -> None:
    solver = ComposableSolver(_Problem(), adapter=_Adapter())

    outcome = solver.step()

    evidence = outcome.metadata["evaluation_disposition"]
    record = solver.evaluation_evidence_journal.get(evidence["event_id"])
    assert record is not None
    assert record.status == "committed"
    assert record.disposition is not None
    assert record.disposition["authority_snapshot_key"] == str(
        solver._latest_snapshot_handle.key
    )
    assert evidence["journal_record"]["status"] == "committed"

    event_snapshot = solver.snapshot_store.read(record.event_snapshot_key)
    authority_snapshot = solver.snapshot_store.read(
        record.verification["destination_snapshot_key"]
    )
    assert event_snapshot is not None and event_snapshot.pinned
    assert authority_snapshot is not None and authority_snapshot.pinned

    release = solver.release_evaluation_evidence_snapshots(evidence["event_id"])

    assert set(release["released_snapshot_keys"]) == {
        record.event_snapshot_key,
        record.verification["destination_snapshot_key"],
    }
    assert solver.snapshot_store.read(record.event_snapshot_key).pinned is False
    assert (
        solver.snapshot_store.read(
            record.verification["destination_snapshot_key"]
        ).pinned
        is False
    )


def test_normal_settlement_defers_until_authority_snapshot_is_readable() -> None:
    class _DelayedReadSnapshotStore(InMemorySnapshotStore):
        def __init__(self) -> None:
            super().__init__()
            self.blocked: set[str] = set()

        def write(self, data, **kwargs):
            handle = super().write(data, **kwargs)
            if isinstance(data, dict) and "last_evaluation_disposition" in data:
                self.blocked.add(str(handle.key))
            return handle

        def read(self, key):
            if str(key) in self.blocked:
                return None
            return super().read(key)

    solver = ComposableSolver(_Problem(), adapter=_Adapter())
    store = _DelayedReadSnapshotStore()
    journal = InMemoryEvaluationEvidenceJournal()
    solver.set_snapshot_store(
        store,
        evaluation_evidence_journal=journal,
    )

    outcome = solver.step()

    evidence = outcome.metadata["evaluation_disposition"]
    record = journal.get(evidence["event_id"])
    assert record is not None
    assert record.status == "deciding"
    assert evidence["journal_settlement"]["status"] == "deferred"

    store.blocked.clear()
    settled = solver.settle_evaluation_disposition(evidence["event_id"])
    assert settled.status == "committed"
    assert settled.terminal_verified


def test_event_must_be_readable_before_acceptance_or_adapter_update() -> None:
    class _UnreadableEventSnapshotStore(InMemorySnapshotStore):
        def read(self, key):
            if "/event/" in str(key):
                return None
            return super().read(key)

    adapter = _Adapter()
    solver = ComposableSolver(_Problem(), adapter=adapter)
    journal = InMemoryEvaluationEvidenceJournal()
    solver.set_snapshot_store(
        _UnreadableEventSnapshotStore(),
        evaluation_evidence_journal=journal,
    )

    with pytest.raises(RuntimeError, match="not durably readable"):
        solver.step()

    records = journal.list_records()
    assert len(records) == 1
    assert records[0].status == "preparing"
    assert adapter.update_calls == 0


def test_recovery_defers_preparing_event_while_snapshot_is_unreadable() -> None:
    solver = ComposableSolver(_Problem(), adapter=_Adapter())
    solver._active_run_id = "run-recovery"
    solver.evaluation_evidence_journal.reserve(
        event_id="event-delayed",
        run_id="run-recovery",
        event_snapshot_key="events/not-yet-readable",
    )

    report = solver.reconcile_evaluation_evidence()

    record = solver.evaluation_evidence_journal.get("event-delayed")
    assert record is not None
    assert record.status == "preparing"
    assert report["status"] == "deferred"
    assert report["deferred_count"] == 1


def test_committed_step_fails_closed_when_disposition_cannot_attach() -> None:
    solver = ComposableSolver(_Problem(), adapter=_Adapter())
    solver.attach_evaluation_disposition_to_pending_snapshot = lambda envelope: False

    with pytest.raises(RuntimeError, match="no staged authority Snapshot"):
        solver.step()

    assert solver._latest_snapshot_handle is None


def test_snapshot_store_replacement_requires_atomic_journal_pair() -> None:
    solver = ComposableSolver(_Problem(), adapter=_Adapter())
    original_store = solver.snapshot_store
    original_journal = solver.evaluation_evidence_journal

    with pytest.raises(ValueError, match="paired EvaluationEvidenceJournal"):
        solver.set_snapshot_store(InMemorySnapshotStore())

    assert solver.snapshot_store is original_store
    assert solver.evaluation_evidence_journal is original_journal
    with pytest.raises(RuntimeError, match="cannot be replaced independently"):
        solver.set_evaluation_evidence_journal(
            InMemoryEvaluationEvidenceJournal()
        )


def test_snapshot_store_replacement_rejects_running_or_published_solver() -> None:
    solver = ComposableSolver(_Problem(), adapter=_Adapter())
    original_store = solver.snapshot_store
    original_journal = solver.evaluation_evidence_journal

    solver.running = True
    with pytest.raises(RuntimeError, match="while Solver is running"):
        solver.set_snapshot_store(
            InMemorySnapshotStore(),
            evaluation_evidence_journal=InMemoryEvaluationEvidenceJournal(),
        )
    solver.running = False
    solver.step()
    with pytest.raises(RuntimeError, match="explicit migration transaction"):
        solver.set_snapshot_store(
            InMemorySnapshotStore(),
            evaluation_evidence_journal=InMemoryEvaluationEvidenceJournal(),
        )

    assert solver.snapshot_store is original_store
    assert solver.evaluation_evidence_journal is original_journal


def test_snapshot_backend_factory_failure_preserves_atomic_pair_and_config(
    monkeypatch,
) -> None:
    import nsgablack.core.blank_solver as blank_solver_module

    solver = ComposableSolver(_Problem(), adapter=_Adapter())
    original_store = solver.snapshot_store
    original_journal = solver.evaluation_evidence_journal
    original_config = (
        solver.snapshot_store_backend,
        solver.snapshot_store_key_prefix,
        solver.snapshot_store_serializer,
    )

    def _fail_journal(**kwargs):
        del kwargs
        raise RuntimeError("journal unavailable")

    monkeypatch.setattr(
        blank_solver_module,
        "create_evaluation_evidence_journal",
        _fail_journal,
    )
    with pytest.raises(RuntimeError, match="journal unavailable"):
        solver.set_snapshot_store_backend(
            "memory",
            key_prefix="replacement",
            serializer="safe",
        )

    assert solver.snapshot_store is original_store
    assert solver.evaluation_evidence_journal is original_journal
    assert (
        solver.snapshot_store_backend,
        solver.snapshot_store_key_prefix,
        solver.snapshot_store_serializer,
    ) == original_config


def test_snapshot_backend_replacement_preflights_before_factory_side_effects(
    monkeypatch,
) -> None:
    import nsgablack.core.blank_solver as blank_solver_module

    solver = ComposableSolver(_Problem(), adapter=_Adapter())
    solver.running = True
    factory_called = False

    def _unexpected_factory(**kwargs):
        nonlocal factory_called
        del kwargs
        factory_called = True
        raise AssertionError("factory must not run")

    monkeypatch.setattr(
        blank_solver_module,
        "build_snapshot_store_or_memory",
        _unexpected_factory,
    )
    with pytest.raises(RuntimeError, match="while Solver is running"):
        solver.set_snapshot_store_backend("filesystem", base_dir="unused")

    assert factory_called is False
