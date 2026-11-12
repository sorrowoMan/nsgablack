"""Known Event versions use one fresh verified view, never a key-only copy."""
from dataclasses import replace

import pytest

from blackbase.context import AuthorityIdentity, SnapshotIdentity, SnapshotIdentityMismatchError
from blackbase.contracts import BatchDisposition
from tests.test_evaluation_evidence_recovery import _Adapter, _Problem
from nsgablack.core import ComposableSolver


def committed_record():
    solver = ComposableSolver(_Problem(), adapter=_Adapter())
    outcome = solver.step()
    event_id = outcome.metadata["evaluation_disposition"]["event_id"]
    return solver, solver.evaluation_evidence_journal.get(event_id)


def test_known_event_uses_one_exact_verified_view_without_key_discovery(monkeypatch):
    solver, record = committed_record()
    expected = SnapshotIdentity.from_dict(record.event_ref)
    store = solver.snapshot_store
    read_view = store.read_verified_view
    reads = []

    def forbidden(key):
        raise AssertionError("known Event must not perform a key-only detached read")

    # The view operation is independent of public detached reads. Capture the
    # real view first so this test measures the inspector's choice of surface.
    actual = read_view(expected)
    monkeypatch.setattr(store, "read_verified_view", lambda identity: (reads.append(identity), actual)[1])
    monkeypatch.setattr(store, "read", forbidden)
    inspection = solver.evaluation_evidence_semantics.inspect_event(record, store)
    assert inspection.state == "verified"
    assert reads == [expected]
    assert inspection.event_ref == expected


@pytest.mark.parametrize("fault", ["missing", "scope", "digest", "key"])
def test_known_event_invalid_or_missing_reference_never_falls_back(monkeypatch, fault):
    solver, record = committed_record()
    store = solver.snapshot_store
    expected = dict(record.event_ref)
    if fault == "scope":
        expected["store_scope"] += ".foreign"
    elif fault == "digest":
        expected["content_digest"] = "sha256:" + "0" * 64
    elif fault == "key":
        expected["key"] += ".foreign"
    if fault == "key":
        with pytest.raises(ValueError, match="event_ref key mismatch"):
            replace(record, event_ref=expected)
        return
    # Inspect a durable pending event, before a terminal receipt binds it to
    # the after-authority. The journal itself rejects inconsistent terminals.
    record = replace(record, phase="event_ready", status="", outcome=None,
                     disposition=None, verification=None, authority_after_ref=None,
                     decision_carrier_ref=None, event_ref=expected)
    calls = []

    def unavailable(identity):
        calls.append(identity)
        if fault == "missing":
            raise KeyError(identity.key)
        raise SnapshotIdentityMismatchError("wrong exact version")

    monkeypatch.setattr(store, "read_verified_view", unavailable)
    monkeypatch.setattr(store, "read", lambda key: pytest.fail("unexpected key fallback"))
    inspection = solver.evaluation_evidence_semantics.inspect_event(record, store)
    assert inspection.state == ("deferred" if fault == "missing" else "invalid")
    assert inspection.reason == ("event_snapshot_unreadable" if fault == "missing" else "event_snapshot_invalid")
    assert len(calls) == (0 if fault == "key" else 1)


def test_legacy_without_reference_still_discovers_and_verifies(monkeypatch):
    solver, record = committed_record()
    store = solver.snapshot_store
    legacy = replace(record, event_ref=None)
    read, verify = store.read, store.read_verified
    calls = []

    def load(key):
        calls.append(("read", key))
        return read(key)

    def check(identity):
        calls.append(("verify", identity.key))
        return verify(identity)

    monkeypatch.setattr(store, "read", load)
    monkeypatch.setattr(store, "read_verified", check)
    inspection = solver.evaluation_evidence_semantics.inspect_event(legacy, store)
    assert inspection.state == "verified"
    assert ("read", record.event_snapshot_key) in calls
    assert ("verify", record.event_snapshot_key) in calls


def pending_decision(record, **overrides):
    fields = dict(phase="decision_ready", status="", verification=None,
                  authority_after_ref=None, decision_carrier_ref=None)
    fields.update(overrides)
    return replace(record, **fields)


def frozen_decision_records(solver, record):
    store = solver.snapshot_store
    identities = [SnapshotIdentity.from_dict(record.event_ref)]
    edge = solver.get_population_authority_identity()
    if edge is not None:
        identities.append(edge.snapshot)
    if record.authority_before_ref is not None:
        identities.append(AuthorityIdentity.from_dict(record.authority_before_ref).snapshot)
    if record.decision_carrier_ref is not None:
        identities.append(SnapshotIdentity.from_dict(record.decision_carrier_ref))
    return {identity: store.read_verified_view(identity) for identity in identities}


def test_first_committed_decision_uses_exact_views_and_rechecks_fence(monkeypatch):
    solver, terminal = committed_record()
    record = pending_decision(terminal)
    assert record.decision_carrier_ref is None
    frozen = frozen_decision_records(solver, terminal)
    calls, fences = [], []
    current = solver.evaluation_evidence_semantics.authority_store.current

    def view(identity):
        calls.append(identity)
        return frozen[identity]

    def fence(key):
        fences.append(key)
        return current(key)

    monkeypatch.setattr(solver.snapshot_store, "read_verified_view", view)
    monkeypatch.setattr(solver.snapshot_store, "read", lambda key: pytest.fail("unnecessary detached read"))
    monkeypatch.setattr(solver.evaluation_evidence_semantics.authority_store, "current", fence)
    result = solver.evaluation_evidence_semantics.inspect_decision(record, solver.snapshot_store)
    assert result.state == "verified"
    assert calls == [SnapshotIdentity.from_dict(record.event_ref), current(fences[0]).snapshot]
    assert len(fences) == 2


@pytest.mark.parametrize("advance", ["snapshot", "epoch"])
def test_read_locator_is_not_reused_as_final_fence_proof(monkeypatch, advance):
    solver, terminal = committed_record()
    record = pending_decision(terminal)
    semantics = solver.evaluation_evidence_semantics
    edge = solver.get_population_authority_identity()
    later = replace(edge, epoch=edge.epoch + 1)
    if advance == "snapshot":
        later_ref = replace(edge.snapshot, key=edge.snapshot.key + ".later")
        later = replace(later, snapshot=later_ref)
    calls = []

    def fence(key):
        calls.append(key)
        return edge if len(calls) == 1 else later

    monkeypatch.setattr(semantics.authority_store, "current", fence)
    result = semantics.inspect_decision(record, solver.snapshot_store)
    assert len(calls) == 2
    assert result.state == "invalid"
    assert result.reason == ("authority_edge_destination_mismatch" if advance == "snapshot"
                             else "authority_edge_epoch_mismatch")


@pytest.mark.parametrize("error", [KeyError, OSError])
def test_decision_known_event_failure_has_no_detached_fallback(monkeypatch, error):
    solver, record = committed_record()
    expected = SnapshotIdentity.from_dict(record.event_ref)

    def missing(identity):
        assert identity == expected
        raise error(identity.key)

    monkeypatch.setattr(solver.snapshot_store, "read_verified_view", missing)
    monkeypatch.setattr(solver.snapshot_store, "read", lambda key: pytest.fail("known ref fallback"))
    result = solver.evaluation_evidence_semantics.inspect_decision(record, solver.snapshot_store)
    assert result.state == "deferred" and result.reason == "event_snapshot_unreadable"


def test_temporary_destination_io_is_deferred_without_detached_fallback(monkeypatch):
    solver, record = committed_record()
    frozen = frozen_decision_records(solver, record)
    event = SnapshotIdentity.from_dict(record.event_ref)
    def view(identity):
        if identity == event:
            return frozen[identity]
        raise OSError("temporary destination outage")
    monkeypatch.setattr(solver.snapshot_store, "read_verified_view", view)
    monkeypatch.setattr(solver.snapshot_store, "read", lambda key: pytest.fail("known ref fallback"))
    result = solver.evaluation_evidence_semantics.inspect_decision(record, solver.snapshot_store)
    assert result.state == "deferred" and result.reason == "destination_snapshot_unreadable"


def test_destination_exact_version_failure_has_no_detached_fallback(monkeypatch):
    solver, record = committed_record()
    frozen = frozen_decision_records(solver, record)
    event = SnapshotIdentity.from_dict(record.event_ref)

    def view(identity):
        if identity == event:
            return frozen[identity]
        raise SnapshotIdentityMismatchError("destination changed")

    monkeypatch.setattr(solver.snapshot_store, "read_verified_view", view)
    monkeypatch.setattr(solver.snapshot_store, "read", lambda key: pytest.fail("known ref fallback"))
    result = solver.evaluation_evidence_semantics.inspect_decision(record, solver.snapshot_store)
    assert result.state == "invalid" and result.reason == "destination_snapshot_invalid"


@pytest.mark.parametrize("failure", [False, True])
def test_noncommitted_decision_uses_its_exact_carrier(monkeypatch, failure):
    class Reject:
        policy_id = "reject-all-test"

        def select(self, candidates, feedback, context):
            return BatchDisposition.prefix(proposed_count=len(candidates.semantic_states),
                                           accepted_count=0, reason="reject")

    class Fail(_Adapter):
        def update(self, control, candidates, feedback, context):
            raise RuntimeError("injected update failure")

    solver = ComposableSolver(_Problem(), adapter=Fail() if failure else _Adapter(),
                              evaluation_acceptance_policy=None if failure else Reject())
    if failure:
        with pytest.raises(RuntimeError, match="injected update failure"):
            solver.step()
    else:
        solver.step()
    record = solver.evaluation_evidence_journal.list_records()[-1]
    assert record.status == ("failed" if failure else "rejected")
    assert record.decision_carrier_ref is not None
    frozen = frozen_decision_records(solver, record)
    calls = []
    monkeypatch.setattr(solver.snapshot_store, "read_verified_view",
                        lambda identity: (calls.append(identity), frozen[identity])[1])
    monkeypatch.setattr(solver.snapshot_store, "read", lambda key: pytest.fail("unnecessary detached read"))
    result = solver.evaluation_evidence_semantics.inspect_decision(record, solver.snapshot_store)
    assert result.state == "verified"
    assert SnapshotIdentity.from_dict(record.decision_carrier_ref) in calls


def test_unfenced_first_destination_remains_deferred(monkeypatch):
    solver, terminal = committed_record()
    record = pending_decision(terminal)
    monkeypatch.setattr(solver.evaluation_evidence_semantics.authority_store, "current", lambda key: None)
    result = solver.evaluation_evidence_semantics.inspect_decision(record, solver.snapshot_store)
    assert result.state == "deferred" and result.reason == "authority_edge_unreadable"
