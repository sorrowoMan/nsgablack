from __future__ import annotations

import numpy as np
import pytest

from blackbase import CandidateBatch, UnknownState
from blackbase.context import AuthorityFenceMismatchError, InMemorySnapshotStore
from blackbase.contracts import BatchDisposition
from blackbase.evaluation import (
    EVALUATION_EVIDENCE_ARCHIVE_KIND,
    EvaluationDispositionEnvelope,
    EvaluationEvidenceArchiveManifest,
    EvaluationEvidenceDeferred,
    EvaluationEvidenceInvalid,
    EvaluationEventEnvelope,
    InMemoryEvaluationEvidenceJournal,
)
from blackbase.resources import ArtifactAuthority, ArtifactBinding, ArtifactPublisher
from nsgablack.adapters import AlgorithmAdapter, CompositeAdapter
from nsgablack.core import BlackBoxProblem, ComposableSolver
from nsgablack.core.state.incumbent import CandidateProvenance
from nsgablack.core.solver_helpers import (
    EVALUATION_EVENT_SNAPSHOT_SCHEMA_V1,
    POPULATION_SNAPSHOT_SCHEMA_V2,
)


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


class _IdentityPopulationAdapter(_Adapter):
    state_recovery_level = "L2"
    population_state_mode = "single"

    def __init__(self, name):
        super().__init__()
        self.name = name
        self.snapshot = None
        self.tokens = ()

    def propose(self, control, context):
        return [UnknownState(values=np.asarray([0.5]), metadata={"source": self.name})]

    def update(self, control, candidates, feedback, context):
        super().update(control, candidates, feedback, context)
        self.set_population_snapshot(candidates, *feedback)
        self.tokens = self.candidate_tokens_for(control, candidates)

    def get_population_snapshot(self):
        return self.snapshot

    def set_population_snapshot(self, population, objectives, violations):
        self.snapshot = self.validate_population_snapshot(population, objectives, violations)
        return True

    def get_population_candidate_tokens(self):
        return self.tokens

    def set_population_candidate_tokens(self, tokens):
        self.tokens = tuple(tokens)
        return True


def _assert_memory_matches_destination(solver):
    owner = solver.population_authority
    edge = solver.get_population_authority_identity()
    destination = solver.snapshot_store.read(owner.snapshot_handle.key)
    assert edge.snapshot == solver.snapshot_store.identity(destination)
    assert owner.mode == destination.data["population_authority"]["authority_mode"]
    payload = destination.data
    if owner.mode == "partitioned":
        assert owner.population is owner.objectives is owner.violations is None
        assert not {"population", "objectives", "constraint_violations"} & payload.keys()
        partitions = payload["population_partitions"]["partitions"]
        assert len(partitions) == len(owner.partitions) == 2
        for stored in partitions:
            partition, batch, provenance = owner.partitions[stored["partition"]["partition_id"]]
            assert partition.as_dict() == stored["partition"]
            assert batch.as_dict() == stored["batch"]
            assert [item.as_dict() for item in provenance] == stored["provenance"]
    else:
        np.testing.assert_array_equal(owner.population, payload["population"])
        np.testing.assert_array_equal(owner.objectives, payload["objectives"])
        np.testing.assert_array_equal(owner.violations, payload["constraint_violations"])
        assert owner.candidate_batch.as_dict() == payload["candidate_batch"]
        assert [item.as_dict() for item in owner.candidate_provenance] == payload["candidate_provenance"]
    return edge


@pytest.mark.parametrize("mode", ["step_batch", "single", "partitioned"])
def test_committed_memory_equals_destination_and_survives_next_failed_step(mode, monkeypatch):
    adapter = {
        "step_batch": lambda: _Adapter(),
        "single": lambda: _IdentityPopulationAdapter("single"),
        "partitioned": lambda: CompositeAdapter((
            _IdentityPopulationAdapter("left"), _IdentityPopulationAdapter("right"))),
    }[mode]()
    solver = ComposableSolver(_Problem(), adapter=adapter)
    outcome = solver.step()
    assert outcome.status == "committed"
    assert solver.population_authority.mode == mode
    before = _assert_memory_matches_destination(solver)
    evidence = solver.evaluation_evidence_journal.get(outcome.metadata["evaluation_disposition"]["event_id"])
    assert before.caused_by_event_identity.as_dict() == evidence.event_ref
    assert before.snapshot.as_dict() == evidence.decision_carrier_ref

    def fail_after_staging(*args, **kwargs):
        raise RuntimeError("fail after staging")

    monkeypatch.setattr(solver, "_update_best", fail_after_staging)
    with pytest.raises(RuntimeError, match="fail after staging"):
        solver.step()
    assert _assert_memory_matches_destination(solver) == before


def test_event_and_decision_errors_share_reason_and_keep_separate_diagnostics(monkeypatch):
    from nsgablack.core import evidence_semantics

    solver = ComposableSolver(_Problem(), adapter=_Adapter())
    outcome = solver.step()
    record = solver.evaluation_evidence_journal.get(outcome.metadata["evaluation_disposition"]["event_id"])

    def invalid(*args, **kwargs):
        raise TypeError("invalid event payload")

    monkeypatch.setattr(evidence_semantics, "validate_evaluation_event_snapshot", invalid)
    for inspect in (solver.evaluation_evidence_semantics.inspect_event,
                    solver.evaluation_evidence_semantics.inspect_decision):
        result = inspect(record, solver.snapshot_store)
        assert result.state == "invalid"
        assert result.reason == "event_snapshot_invalid"
        assert result.diagnostics["error_type"] == "TypeError"
        assert result.diagnostics["message"] == "invalid event payload"


@pytest.mark.parametrize("missing", ["event", "predecessor", "destination", "authority"])
def test_unreadable_evidence_keeps_explicit_deferred_classification(missing, monkeypatch):
    solver = ComposableSolver(_Problem(), adapter=_Adapter())
    solver.step()  # Give the second event a durable predecessor.
    outcome = solver.step()
    record = solver.evaluation_evidence_journal.get(outcome.metadata["evaluation_disposition"]["event_id"])
    if missing in {"event", "destination"}:
        read = solver.snapshot_store.read
        key = record.event_snapshot_key if missing == "event" else record.verification["destination_snapshot_key"]
        monkeypatch.setattr(solver.snapshot_store, "read", lambda candidate: None if candidate == key else read(candidate))
    elif missing == "predecessor":
        def unreadable(*args, **kwargs):
            raise KeyError("predecessor temporarily unavailable")
        monkeypatch.setattr(solver.snapshot_store, "read_verified", unreadable)
    else:
        monkeypatch.setattr(solver.evaluation_evidence_semantics.authority_store, "current", lambda key: None)
    inspection = solver.evaluation_evidence_semantics.inspect_decision(record, solver.snapshot_store)
    assert inspection.state == "deferred"
    assert inspection.reason == {
        "event": "event_snapshot_unreadable", "predecessor": "event_predecessor_unreadable",
        "destination": "destination_snapshot_unreadable", "authority": "authority_edge_unreadable",
    }[missing]


def test_reinspection_timestamp_changes_without_mutating_evidence_identity(monkeypatch):
    from types import SimpleNamespace
    from nsgablack.core import evidence_semantics

    solver = ComposableSolver(_Problem(), adapter=_Adapter())
    outcome = solver.step()
    record = solver.evaluation_evidence_journal.get(outcome.metadata["evaluation_disposition"]["event_id"])
    before = solver.get_population_authority_identity()
    inspections = []
    for timestamp in (100.0, 200.0):
        monkeypatch.setattr(evidence_semantics, "time", SimpleNamespace(time=lambda: timestamp))
        inspections.append(solver.evaluation_evidence_semantics.inspect_decision(record, solver.snapshot_store))
    first, second = inspections
    assert first.state == second.state == "verified"
    assert first.verification.verified_at == 100.0
    assert second.verification.verified_at == 200.0
    first_receipt, second_receipt = first.verification.as_dict(), second.verification.as_dict()
    first_receipt.pop("verified_at")
    second_receipt.pop("verified_at")
    assert first_receipt == second_receipt
    assert first.event_ref == second.event_ref
    assert first.decision_carrier_ref == second.decision_carrier_ref == before.snapshot
    assert solver.get_population_authority_identity() == before
    assert solver.evaluation_evidence_journal.get(record.event_id) == record


def _event(event_id: str, run_id: str, snapshot_key: str) -> EvaluationEventEnvelope:
    return EvaluationEventEnvelope(
        event_id=event_id,
        candidate_codec="test.candidate/v1",
        candidate_payload={"rows": [[0.5]]},
        feedback_codec="test.feedback/v1",
        feedback_payload={"objectives": [[0.25]]},
        identity={
            "run_id": run_id,
            "event_snapshot_key": snapshot_key,
            "authority_before_ref": None,
        },
        evaluation_count=1,
    )


def _write_event_snapshot(
    solver,
    event: EvaluationEventEnvelope,
    key: str,
    *,
    legacy: bool = False,
) -> None:
    if legacy:
        payload = {
            "last_evaluation_event": {
                "evaluation_event_envelope": event.as_dict(),
            }
        }
        schema = "nsgablack.population_snapshot/v2"
    else:
        payload = {
            "evaluation_event": event.as_dict(),
            "authority_before_ref": None,
        }
        schema = EVALUATION_EVENT_SNAPSHOT_SCHEMA_V1
    solver.snapshot_store.write(
        payload,
        key=key,
        schema=schema,
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


def _publish_evidence_archive(tmp_path, manifest):
    publisher = ArtifactPublisher(
        ArtifactAuthority(root=str(tmp_path / "artifacts"), namespace="test"),
        project_run_id="project-run",
        case_run_id="case-run",
    )
    name = f"evaluation-evidence-{manifest.event_id}"
    transaction_id = f"archive-{manifest.event_id}"
    publisher.reserve_publication(name, transaction_id)
    ref = publisher.publish(
        name,
        manifest.as_dict(),
        serializer="json",
        kind=EVALUATION_EVIDENCE_ARCHIVE_KIND,
        media_type="application/json",
        metadata=manifest.artifact_metadata(),
    )
    publisher.record_provisional_publication(name, transaction_id, ref)
    receipt = publisher.commit_publications(
        transaction_id,
        {name: ref},
        metadata={"case_finalization_sealed": True},
    )[name]
    return ArtifactBinding(ref=ref, publication=receipt), publisher.publication_ledger


class _ArchiveCaseRuntime:
    def __init__(self, tmp_path) -> None:
        self.artifact_publisher = ArtifactPublisher(
            ArtifactAuthority(
                root=str(tmp_path / "case-artifacts"),
                namespace="case-test",
            ),
            project_run_id="project-run",
            case_run_id="case-run",
        )
        self.transaction_id = "case-finalization"
        self.refs = {}
        self.observers = []

    def publish_artifact(self, name, value, **kwargs):
        self.artifact_publisher.reserve_publication(name, self.transaction_id)
        ref = self.artifact_publisher.publish(name, value, **kwargs)
        self.artifact_publisher.record_provisional_publication(
            name,
            self.transaction_id,
            ref,
        )
        self.refs[name] = ref
        return ref

    def register_finalization_observer(self, observer, *, name=""):
        self.observers.append((name, observer))

    def seal(self):
        receipts = self.artifact_publisher.commit_publications(
            self.transaction_id,
            self.refs,
            metadata={"case_finalization_sealed": True},
        )
        for _, observer in self.observers:
            observer(receipts)
        return receipts


@pytest.mark.parametrize("legacy", (False, True))
def test_recovery_archives_pending_event_without_replaying_policy_or_adapter(
    legacy,
) -> None:
    adapter = _Adapter()
    solver = ComposableSolver(_Problem(), adapter=adapter)
    solver._active_run_id = "run-recovery"
    event_id = "event-pending"
    event_key = "evaluation-evidence/event/event-pending"
    event = _event(event_id, solver._active_run_id, event_key)
    _write_event_snapshot(solver, event, event_key, legacy=legacy)
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


def test_event_publication_failure_stops_before_acceptance_policy() -> None:
    class _FailingEventStore(InMemorySnapshotStore):
        def write(self, data, **kwargs):
            if kwargs.get("schema") == EVALUATION_EVENT_SNAPSHOT_SCHEMA_V1:
                raise OSError("event store unavailable")
            return super().write(data, **kwargs)

    class _Policy:
        def __init__(self) -> None:
            self.calls = 0

        def select(self, candidates, feedback, context):
            del feedback, context
            self.calls += 1
            return BatchDisposition.prefix(
                proposed_count=len(candidates.semantic_states),
                accepted_count=len(candidates.semantic_states),
                reason="test",
            )

    adapter = _Adapter()
    policy = _Policy()
    solver = ComposableSolver(
        _Problem(),
        adapter=adapter,
        evaluation_acceptance_policy=policy,
    )
    journal = InMemoryEvaluationEvidenceJournal()
    solver.set_snapshot_store(
        _FailingEventStore(),
        evaluation_evidence_journal=journal,
    )

    with pytest.raises(OSError, match="event store unavailable"):
        solver.step()

    assert policy.calls == 0
    assert adapter.update_calls == 0
    assert [record.status for record in journal.list_records()] == ["preparing"]


def test_event_reader_dispatches_strictly_by_snapshot_schema() -> None:
    solver = ComposableSolver(_Problem(), adapter=_Adapter())
    event_key = "events/direct-in-population-schema"
    event = _event("event-direct", "run-direct", event_key)
    solver.snapshot_store.write(
        {
            "evaluation_event": event.as_dict(),
            "authority_before_ref": None,
        },
        key=event_key,
        schema=POPULATION_SNAPSHOT_SCHEMA_V2,
    )
    with pytest.raises(ValueError, match="must not contain the Event v1 slot"):
        solver.read_evaluation_event_snapshot(event_key)

    legacy_key = "events/legacy-in-event-schema"
    legacy = _event("event-legacy", "run-legacy", legacy_key)
    solver.snapshot_store.write(
        {
            "last_evaluation_event": {
                "evaluation_event_envelope": legacy.as_dict(),
            }
        },
        key=legacy_key,
        schema=EVALUATION_EVENT_SNAPSHOT_SCHEMA_V1,
    )
    with pytest.raises(ValueError, match="missing evaluation_event"):
        solver.read_evaluation_event_snapshot(legacy_key)


def test_recovery_rejects_event_with_mismatched_snapshot_identity() -> None:
    solver = ComposableSolver(_Problem(), adapter=_Adapter())
    solver._active_run_id = "run-recovery"
    event_id = "event-invalid-identity"
    event_key = "evaluation-evidence/event/event-invalid-identity"
    event_payload = _event(event_id, solver._active_run_id, event_key).as_dict()
    event_payload["identity"]["event_snapshot_key"] = "events/other"
    solver.snapshot_store.write(
        {
            "evaluation_event": event_payload,
            "authority_before_ref": None,
        },
        key=event_key,
        schema=EVALUATION_EVENT_SNAPSHOT_SCHEMA_V1,
    )
    solver.evaluation_evidence_journal.reserve(
        event_id=event_id,
        run_id=solver._active_run_id,
        event_snapshot_key=event_key,
    )

    report = solver.reconcile_evaluation_evidence()

    record = solver.evaluation_evidence_journal.get(event_id)
    assert record is not None
    assert record.status == "abandoned"
    assert record.metadata["abandon_reason"] == "event_snapshot_invalid"
    assert report["records"][0]["reason"] == "event_snapshot_invalid"


def test_event_full_authority_edge_must_match_journal_reservation() -> None:
    solver = ComposableSolver(_Problem(), adapter=_Adapter())
    solver.step()
    before = solver.get_population_authority_identity()
    assert before is not None

    event_id = "event-tampered-authority-edge"
    event_key = f"evaluation-evidence/event/{event_id}"
    tampered_edge = before.as_dict()
    tampered_edge["epoch"] = before.epoch + 7
    envelope = _event(event_id, solver._evaluation_evidence_run_id(), event_key)
    envelope_payload = envelope.as_dict()
    envelope_payload["identity"].update(
        {
            "authority_before_ref": before.snapshot.as_dict(),
            "authority_snapshot_key": before.snapshot.key,
            "authority_before_edge": tampered_edge,
        }
    )
    solver.snapshot_store.put_immutable(
        {
            "evaluation_event": envelope_payload,
            "authority_before_ref": before.snapshot.as_dict(),
        },
        key=event_key,
        schema=EVALUATION_EVENT_SNAPSHOT_SCHEMA_V1,
    )
    reserved = solver.evaluation_evidence_journal.reserve(
        event_id=event_id,
        run_id=solver._evaluation_evidence_run_id(),
        event_snapshot_key=event_key,
        authority_before_ref=before,
    )

    with pytest.raises(
        EvaluationEvidenceInvalid,
        match="Authority edge disagrees",
    ):
        solver.evaluation_evidence_coordinator.confirm_event(
            event_id,
            expected_revision=reserved.revision,
        )


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


def test_normal_step_closes_journal_to_same_committed_disposition(tmp_path) -> None:
    solver = ComposableSolver(_Problem(), adapter=_Adapter())

    outcome = solver.step()

    evidence = outcome.metadata["evaluation_disposition"]
    record = solver.evaluation_evidence_journal.get(evidence["event_id"])
    assert record is not None
    assert record.status == "committed"
    assert record.phase == "finalized"
    assert record.outcome == "accepted"
    assert record.event_ref is not None
    assert record.authority_after_ref is not None
    assert record.decision_carrier_ref is not None
    assert record.authority_after_ref["snapshot"] == record.decision_carrier_ref
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

    manifest = EvaluationEvidenceArchiveManifest.from_record(
        record,
        snapshots=solver.snapshot_store,
    )
    binding, ledger = _publish_evidence_archive(tmp_path, manifest)
    solver.evaluation_evidence_coordinator.archive_verifier = ledger
    release = solver.release_evaluation_evidence_snapshots(
        evidence["event_id"],
        manifest=manifest,
        archive_binding=binding,
    )

    assert set(release["snapshot_results"]) == {
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
    archived = solver.evaluation_evidence_journal.get(evidence["event_id"])
    assert archived is not None
    assert archived.archive_binding == binding.as_dict()
    assert archived.retention_released is True


def test_population_authority_epoch_is_independent_and_fences_stale_steps() -> None:
    solver = ComposableSolver(_Problem(), adapter=_Adapter())
    solver.step()
    first = solver.get_population_authority_identity()
    assert first is not None
    stale_plan = solver._authority_commit_plan()

    solver.step()
    second = solver.get_population_authority_identity()
    assert second is not None
    assert (first.epoch, second.epoch) == (1, 2)
    assert first.snapshot.revision == second.snapshot.revision == 1

    current = solver.snapshot_store.read_verified(second.snapshot)
    stale_record = {
        "data": dict(current.data),
        "key": "authority/stale-writer",
        "meta": {"test": "stale-fence"},
        "schema": current.schema,
        "ttl_seconds": None,
        "generation": solver.generation,
        "publication": "authority",
        "authority_commit": stale_plan,
    }
    with pytest.raises(AuthorityFenceMismatchError):
        solver._write_snapshot_record(stale_record, strict=True)

    assert solver.get_population_authority_identity() == second


def test_next_step_fails_closed_until_prior_decision_converges(monkeypatch) -> None:
    adapter = _Adapter()
    solver = ComposableSolver(_Problem(), adapter=adapter)
    normal_settle = solver.settle_evaluation_disposition

    def _defer_live_settlement(event_id):
        raise RuntimeError(f"deferred live settlement: {event_id}")

    monkeypatch.setattr(solver, "settle_evaluation_disposition", _defer_live_settlement)
    first_outcome = solver.step()
    first_event_id = first_outcome.metadata["evaluation_disposition"]["event_id"]
    first_record = solver.evaluation_evidence_journal.get(first_event_id)
    first_authority = solver.get_population_authority_identity()
    assert first_record is not None and first_record.phase == "decision_ready"
    assert first_authority is not None and first_authority.epoch == 1
    assert adapter.update_calls == 1

    coordinator = solver.evaluation_evidence_coordinator
    normal_coordinator_settle = coordinator.settle_decision

    def _defer_recovery(*args, **kwargs):
        del args, kwargs
        raise EvaluationEvidenceDeferred("test storage outage")

    monkeypatch.setattr(coordinator, "settle_decision", _defer_recovery)
    with pytest.raises(
        EvaluationEvidenceDeferred,
        match="prior evaluation evidence must converge",
    ):
        solver.step()
    assert adapter.update_calls == 1
    assert solver.get_population_authority_identity() == first_authority

    monkeypatch.setattr(coordinator, "settle_decision", normal_coordinator_settle)
    monkeypatch.setattr(solver, "settle_evaluation_disposition", normal_settle)
    solver.step()

    settled = solver.evaluation_evidence_journal.get(first_event_id)
    current = solver.get_population_authority_identity()
    assert settled is not None and settled.phase == "finalized"
    assert current is not None and current.epoch == 2
    assert adapter.update_calls == 2


def test_rejected_step_uses_persisted_authority_when_local_handle_is_absent() -> None:
    class _RejectAll:
        def select(self, candidates, feedback, context):
            del feedback, context
            return BatchDisposition.prefix(
                proposed_count=len(candidates.semantic_states),
                accepted_count=0,
                reason="test rejection",
            )

    adapter = _Adapter()
    solver = ComposableSolver(_Problem(), adapter=adapter)
    solver.step()
    before = solver.get_population_authority_identity()
    assert before is not None

    solver._latest_snapshot_handle = None
    solver.evaluation_acceptance_policy = _RejectAll()
    rejected = solver.step()

    evidence = rejected.metadata["evaluation_disposition"]
    record = solver.evaluation_evidence_journal.get(evidence["event_id"])
    assert rejected.committed is False
    assert record is not None and record.outcome == "rejected"
    assert record.disposition is not None
    assert record.disposition["authority_snapshot_key"] == before.snapshot.key
    assert solver.get_population_authority_identity() == before


def test_case_finalization_archives_before_releasing_evidence(tmp_path) -> None:
    solver = ComposableSolver(_Problem(), adapter=_Adapter())
    outcome = solver.step()
    event_id = outcome.metadata["evaluation_disposition"]["event_id"]
    before = solver.evaluation_evidence_journal.get(event_id)
    assert before is not None and before.retention_released is False
    assert solver.snapshot_store.read(before.event_ref["key"]).pinned is True

    runtime = _ArchiveCaseRuntime(tmp_path)
    solver.set_case_runtime(runtime)
    staged = solver.stage_evaluation_evidence_archives()

    assert set(staged) == {event_id}
    during = solver.evaluation_evidence_journal.get(event_id)
    assert during is not None and during.archive_binding is None
    assert solver.snapshot_store.read(during.event_ref["key"]).pinned is True

    runtime.seal()

    archived = solver.evaluation_evidence_journal.get(event_id)
    assert archived is not None
    assert archived.archive_binding is not None
    assert archived.retention_released is True
    assert solver.snapshot_store.read(archived.event_ref["key"]).pinned is False
    assert (
        solver.snapshot_store.read(archived.decision_carrier_ref["key"]).pinned
        is False
    )


def test_bound_archive_release_redrives_without_process_staging(
    tmp_path,
    monkeypatch,
) -> None:
    solver = ComposableSolver(_Problem(), adapter=_Adapter())
    outcome = solver.step()
    event_id = outcome.metadata["evaluation_disposition"]["event_id"]
    runtime = _ArchiveCaseRuntime(tmp_path)
    solver.set_case_runtime(runtime)
    solver.stage_evaluation_evidence_archives()

    journal = solver.evaluation_evidence_journal
    normal_mark = journal.mark_retention_released

    def _lose_release_ack(*args, **kwargs):
        del args, kwargs
        raise OSError("journal acknowledgement unavailable")

    monkeypatch.setattr(journal, "mark_retention_released", _lose_release_ack)
    with pytest.raises(OSError, match="journal acknowledgement unavailable"):
        runtime.seal()

    interrupted = journal.get(event_id)
    assert interrupted is not None
    assert interrupted.archive_binding is not None
    assert interrupted.retention_released is False

    monkeypatch.setattr(journal, "mark_retention_released", normal_mark)
    solver._evaluation_evidence_archive_staging = {}
    resumed = solver.stage_evaluation_evidence_archives()

    assert set(resumed) == {event_id}
    recovered = journal.get(event_id)
    assert recovered is not None and recovered.retention_released is True


def test_authority_commit_stays_recoverable_until_snapshot_is_readable() -> None:
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

    with pytest.raises(KeyError, match="Snapshot identity is no longer readable"):
        solver.step()

    records = journal.list_records()
    assert len(records) == 1
    record = records[0]
    assert record is not None
    assert record.status == "deciding"
    assert record.outcome == "accepted"
    assert solver.get_population_authority_identity() is None

    store.blocked.clear()
    report = solver.reconcile_evaluation_evidence(record.run_id)
    settled = journal.get(record.event_id)
    assert report["settled_count"] == 1
    assert settled is not None
    assert settled.status == "committed"
    assert settled.terminal_verified
    authority = solver.get_population_authority_identity()
    assert authority is not None
    assert authority.snapshot.key == settled.decision_carrier_ref["key"]


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
