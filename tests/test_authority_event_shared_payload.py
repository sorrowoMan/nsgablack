from __future__ import annotations

from collections.abc import Mapping
from dataclasses import replace

import numpy as np
import pytest

from blackbase import CandidateBatch, Feedback, UnknownState
from blackbase.evaluation import EvaluationEventEnvelope
from nsgablack.adapters import AlgorithmAdapter, PopulationPartition
from nsgablack.core import BlackBoxProblem, ComposableSolver
from nsgablack.core.evaluation_feedback import OptimizationFeedbackBatch
from nsgablack.core.solver_helpers import (
    EVALUATION_EVENT_KEY,
    LAST_EVALUATED_BATCH_KEY,
    LAST_EVALUATION_EVENT_KEY,
    POPULATION_SNAPSHOT_SCHEMA_V2,
    PartitionedPopulationSnapshotError,
    population_snapshot_authority_mode,
    require_single_population_payload,
    validate_population_snapshot_v2,
)
from nsgablack.core.state.incumbent import CandidateProvenance
from nsgablack.plugins.system.checkpoint_resume import (
    CheckpointResumeConfig,
    CheckpointResumePlugin,
)


class _Problem(BlackBoxProblem):
    def __init__(self) -> None:
        super().__init__(
            dimension=2,
            objectives=["minimize"],
            bounds=[(-1.0, 1.0)] * 2,
        )

    def evaluate(self, candidate):
        raise AssertionError("shared-payload tests must not execute the Problem")


class _NoRunAdapter(AlgorithmAdapter):
    def __init__(self) -> None:
        super().__init__(name="shared-payload-test")

    def propose(self, control, context):
        raise AssertionError("shared-payload tests must not execute search")

    def update(self, control, candidates, feedback, context):
        raise AssertionError("shared-payload tests must not execute search")


def _solver(**kwargs) -> ComposableSolver:
    return ComposableSolver(
        _Problem(),
        adapter=_NoRunAdapter(),
        snapshot_strict=True,
        **kwargs,
    )


def _record_event(solver, *, publish=True):
    values = np.asarray([[0.25, 0.5], [-0.25, 0.75]])
    batch = CandidateBatch(
        semantic_states=tuple(
            UnknownState(values=row, metadata={"model_family": "test", "row": index})
            for index, row in enumerate(values)
        ),
        numeric_matrix=values,
        candidate_tokens=("candidate-a", "candidate-b"),
    )
    feedback = OptimizationFeedbackBatch.from_feedback(
        tuple(
            Feedback(
                objectives=np.asarray([7.0 + index]),
                metrics={"validation_loss": 1.0 + index},
                info={
                    "constraint_violation": 0.0,
                    "raw_evaluation": {
                        "objectives": [1.0 + index],
                        "constraint_violation": 0.25 + index,
                    },
                },
            )
            for index in range(2)
        ),
        metadata={"provider": "published-provider"},
    )
    provenance = tuple(
        CandidateProvenance(
            candidate_token=token,
            source_kind="proposal",
            source_run_id="shared-payload-run",
            proposal_id=f"proposal-{index}",
            metadata={"lineage": "original"},
        )
        for index, token in enumerate(batch.candidate_tokens)
    )
    solver.evaluation_count = 2
    solver.record_evaluation_event(batch, feedback, provenance)
    if publish:
        assert solver.write_evaluation_event_snapshot()
    return batch, feedback, provenance


def _publish_authority(solver, batch, feedback, provenance):
    solver.commit_candidate_population(
        batch.numeric_matrix,
        batch.candidate_tokens,
        sources=((batch, provenance),),
    )
    assert solver.write_population_snapshot(
        batch.numeric_matrix, feedback.objectives, feedback.violations
    )
    identity = solver.get_population_authority_identity()
    assert identity is not None
    return identity.snapshot


def _event_identity(solver):
    handle = solver._latest_evaluation_snapshot_handle
    assert handle is not None
    return solver.snapshot_store.identity(handle)


def _delete_event(solver):
    identity = _event_identity(solver)
    owner = solver.evaluation_evidence_coordinator.retention_owner(
        solver._last_evaluation_event_id
    )
    # This isolated test deliberately ends retention to test value independence;
    # it does not claim an archive receipt or run the release state machine.
    solver.snapshot_store.unpin(identity.key, owner=owner)
    solver.snapshot_store.delete(identity.key)
    assert solver.snapshot_store.read(identity.key) is None


def _assert_complete_event(slot, batch, feedback):
    envelope = EvaluationEventEnvelope.from_dict(slot["evaluation_event_envelope"])
    assert envelope.semantic_complete is True
    restored_batch = CandidateBatch.from_dict(envelope.candidate_payload)
    restored_feedback = OptimizationFeedbackBatch.from_dict(envelope.feedback_payload)
    assert restored_batch.candidate_tokens == batch.candidate_tokens
    assert dict(restored_batch.semantic_states[1].metadata) == {
        "model_family": "test", "row": 1
    }
    np.testing.assert_array_equal(restored_batch.numeric_matrix, batch.numeric_matrix)
    np.testing.assert_array_equal(restored_feedback.objectives, feedback.objectives)
    np.testing.assert_array_equal(restored_feedback.violations, feedback.violations)
    np.testing.assert_array_equal(restored_feedback.raw_objectives, [[1.0], [2.0]])
    np.testing.assert_array_equal(restored_feedback.raw_violations, [0.25, 1.25])
    assert restored_feedback.metadata["provider"] == "published-provider"
    assert envelope.provenance[1]["proposal_id"] == "proposal-1"
    assert envelope.evaluation_count == 2
    np.testing.assert_array_equal(slot["population"], batch.numeric_matrix)
    np.testing.assert_array_equal(slot["objectives"], feedback.objectives)
    np.testing.assert_array_equal(slot["constraint_violations"], feedback.violations)
    return envelope


def _forbid_reexport():
    raise AssertionError("a published Event must not fall back to its memory copy")


def _allow_only_authority_verified_views(solver, monkeypatch):
    read_view = solver.snapshot_store.read_verified_view

    def authority_only(identity):
        assert identity.schema == POPULATION_SNAPSHOT_SCHEMA_V2, (
            "an unpublished or portable Event must use its complete local value "
            "without reading a source Event identity"
        )
        return read_view(identity)

    monkeypatch.setattr(solver.snapshot_store, "read_verified_view", authority_only)


def test_memory_authority_reuses_verified_event_nodes_and_remains_self_contained(
    monkeypatch,
):
    solver = _solver()
    batch, feedback, provenance = _record_event(solver)
    event_identity = _event_identity(solver)
    event = solver.snapshot_store.read_verified_view(event_identity)
    published = event.data[EVALUATION_EVENT_KEY]
    monkeypatch.setattr(solver, "export_evaluation_event_checkpoint_state", _forbid_reexport)
    solver._last_evaluated_event_arrays = tuple(
        np.full_like(value, -999.0) for value in solver._last_evaluated_event_arrays
    )

    authority_identity = _publish_authority(solver, batch, feedback, provenance)
    authority = solver.snapshot_store.read_verified_view(authority_identity)
    slot = authority.data[LAST_EVALUATION_EVENT_KEY]

    assert isinstance(authority.data, Mapping)
    assert authority.schema == POPULATION_SNAPSHOT_SCHEMA_V2
    assert slot["evaluation_event_envelope"] is published
    assert slot["candidate_batch"] is published["candidate_payload"]
    assert slot["candidate_provenance"] is published["provenance"]
    for field in ("population", "objectives", "constraint_violations"):
        assert isinstance(authority.data[field], np.ndarray)
    validate_population_snapshot_v2(
        authority.data, snapshot_schema=authority.schema,
        expected_authority_mode="step_batch",
    )
    with pytest.raises(TypeError):
        published["feedback_payload"]["metadata"]["provider"] = "mutated"
    _assert_complete_event(slot, batch, feedback)

    _delete_event(solver)

    surviving = solver.snapshot_store.read_verified(authority_identity)
    _assert_complete_event(surviving.data[LAST_EVALUATION_EVENT_KEY], batch, feedback)
    assert surviving.data[LAST_EVALUATION_EVENT_KEY]["evaluation_event_envelope"] is not published


def test_published_empty_event_preserves_numeric_projection_shapes(monkeypatch):
    solver = _solver()
    batch = CandidateBatch.from_candidates(())
    feedback = OptimizationFeedbackBatch.from_arrays(np.empty((0, 2)), [])
    solver.record_evaluation_event(batch, feedback, ())
    assert solver.write_evaluation_event_snapshot()
    event = solver.snapshot_store.read_verified_view(_event_identity(solver))
    published = event.data[EVALUATION_EVENT_KEY]
    monkeypatch.setattr(solver, "export_evaluation_event_checkpoint_state", _forbid_reexport)

    identity = _publish_authority(solver, batch, feedback, ())
    authority = solver.snapshot_store.read_verified_view(identity)
    slot = authority.data[LAST_EVALUATION_EVENT_KEY]

    assert slot["evaluation_event_envelope"] is published
    assert slot["candidate_batch"] is published["candidate_payload"]
    assert slot["candidate_provenance"] is published["provenance"]
    assert slot["population"].shape == (0, 0)
    assert slot["objectives"].shape == (0, 2)
    assert slot["constraint_violations"].shape == (0,)
    assert authority.data["population"].shape == (0, 0)
    assert authority.data["objectives"].shape == (0, 2)
    assert authority.data["constraint_violations"].shape == (0,)
    envelope = EvaluationEventEnvelope.from_dict(slot["evaluation_event_envelope"])
    assert envelope.semantic_complete is True
    assert len(envelope.provenance) == 0
    assert envelope.identity["event_snapshot_key"] == event.key


@pytest.mark.parametrize("reader", ["read", "read_verified"])
def test_ordinary_event_reads_remain_detached_from_shared_authority(reader):
    solver = _solver()
    batch, feedback, provenance = _record_event(solver)
    event_identity = _event_identity(solver)
    authority_identity = _publish_authority(solver, batch, feedback, provenance)
    argument = event_identity.key if reader == "read" else event_identity
    detached = getattr(solver.snapshot_store, reader)(argument)
    assert detached is not None
    detached.data[EVALUATION_EVENT_KEY]["feedback_payload"]["metadata"]["provider"] = "mutated"
    detached.data[EVALUATION_EVENT_KEY]["candidate_payload"]["numeric_matrix"][0][0] = 999.0

    event = solver.snapshot_store.read_verified_view(event_identity)
    authority = solver.snapshot_store.read_verified_view(authority_identity)
    assert event.data[EVALUATION_EVENT_KEY]["feedback_payload"]["metadata"]["provider"] == "published-provider"
    _assert_complete_event(authority.data[LAST_EVALUATION_EVENT_KEY], batch, feedback)


@pytest.mark.parametrize("damage", ["scope", "revision", "digest", "missing", "body"])
def test_known_published_event_identity_failure_never_falls_back_to_memory(
    damage, monkeypatch,
):
    solver = _solver()
    batch, feedback, provenance = _record_event(solver)
    handle = solver._latest_evaluation_snapshot_handle
    if damage == "body":
        detached = solver.snapshot_store.read_verified(_event_identity(solver))
        detached.data[EVALUATION_EVENT_KEY]["feedback_payload"]["metadata"]["provider"] = "body-tampered"
        solver.snapshot_store._data[handle.key] = replace(
            solver.snapshot_store._data[handle.key], data=detached.data
        )
    elif damage == "missing":
        _delete_event(solver)
    else:
        changes = {
            "scope": {"store_scope": "foreign-snapshot-scope"},
            "revision": {"revision": handle.revision + 1},
            "digest": {"content_digest": "sha256:" + "0" * 64},
        }[damage]
        invalid_handle = replace(handle, **changes)
        solver._latest_evaluation_snapshot_handle = invalid_handle
        evidence = dict(solver._last_evaluation_evidence_record)
        evidence["event_ref"] = invalid_handle.identity().as_dict()
        solver._last_evaluation_evidence_record = evidence
    monkeypatch.setattr(solver, "export_evaluation_event_checkpoint_state", _forbid_reexport)

    with pytest.raises((KeyError, ValueError, RuntimeError)):
        _publish_authority(solver, batch, feedback, provenance)

    assert solver.get_population_authority_identity() is None
    assert solver._latest_snapshot_handle is None
    assert solver._last_evaluated_event_batch is not None


def test_disagreeing_published_event_identities_are_rejected(monkeypatch):
    solver = _solver()
    batch, feedback, provenance = _record_event(solver)
    handle = solver._latest_evaluation_snapshot_handle
    solver._latest_evaluation_snapshot_handle = replace(handle, revision=handle.revision + 1)
    monkeypatch.setattr(solver, "export_evaluation_event_checkpoint_state", _forbid_reexport)

    with pytest.raises(ValueError, match="identities disagree"):
        _publish_authority(solver, batch, feedback, provenance)
    assert solver.get_population_authority_identity() is None


def test_unpublished_semantic_event_keeps_full_authority_payload(monkeypatch):
    solver = _solver()
    batch, feedback, provenance = _record_event(solver, publish=False)
    _allow_only_authority_verified_views(solver, monkeypatch)

    identity = _publish_authority(solver, batch, feedback, provenance)
    authority = solver.snapshot_store.read_verified(identity)

    assert solver._latest_evaluation_snapshot_handle is None
    envelope = _assert_complete_event(authority.data[LAST_EVALUATION_EVENT_KEY], batch, feedback)
    assert "event_snapshot_key" not in envelope.identity


def test_legacy_incomplete_event_keeps_numeric_authority_data(monkeypatch):
    solver = _solver()
    values = np.asarray([[0.25, 0.5]])
    objectives = np.asarray([[3.0]])
    violations = np.asarray([0.75])
    legacy = EvaluationEventEnvelope(
        event_id="migrated:legacy-run:1",
        candidate_codec="blackbase.numeric_candidate_batch/v1",
        candidate_payload={"population": values.tolist()},
        feedback_codec="nsgablack.numeric_optimization_feedback/v1",
        feedback_payload={
            "objectives": objectives.tolist(),
            "constraint_violations": violations.tolist(),
        },
        identity={"run_id": "legacy-run", "logical_step": 1},
        evaluation_count=1,
        semantic_complete=False,
    )
    solver.restore_evaluation_event_checkpoint_state(legacy.as_dict())
    _allow_only_authority_verified_views(solver, monkeypatch)

    assert solver.write_population_snapshot(values, objectives, violations)
    authority = solver.snapshot_store.read_verified(
        solver.get_population_authority_identity().snapshot
    )
    slot = authority.data[LAST_EVALUATION_EVENT_KEY]
    assert "evaluation_event_envelope" not in slot
    assert "candidate_batch" not in slot
    np.testing.assert_array_equal(slot["population"], values)
    np.testing.assert_array_equal(slot["objectives"], objectives)
    np.testing.assert_array_equal(slot["constraint_violations"], violations)
    assert solver._last_evaluation_event_id == legacy.event_id
    assert solver._last_evaluated_event_batch is None


def test_portable_checkpoint_restores_full_event_in_a_different_store(monkeypatch):
    source = _solver()
    batch, feedback, provenance = _record_event(source)
    _publish_authority(source, batch, feedback, provenance)
    writer = CheckpointResumePlugin(config=CheckpointResumeConfig(save_on_finish=False))
    writer.attach(source)
    payload = writer._build_payload(solver=source, reason="portable-shared-event")
    saved_event_id = payload["solver_state"]["evaluation_event"]["event_id"]
    _delete_event(source)

    target = _solver()
    assert target.snapshot_store.store_scope != source.snapshot_store.store_scope
    _allow_only_authority_verified_views(target, monkeypatch)
    reader = CheckpointResumePlugin(config=CheckpointResumeConfig(save_on_finish=False))
    reader.attach(target)

    reader._apply_solver_state(target, payload["solver_state"], 0)

    identity = target.get_population_authority_identity()
    assert identity is not None
    authority = target.snapshot_store.read_verified(identity.snapshot)
    restored = _assert_complete_event(authority.data[LAST_EVALUATION_EVENT_KEY], batch, feedback)
    assert restored.event_id == saved_event_id
    assert target.evaluation_count == source.evaluation_count == 2
    assert target._latest_evaluation_snapshot_handle is None
    assert target.snapshot_store.read(restored.identity["event_snapshot_key"]) is None


def test_file_authority_remains_complete_after_source_event_is_deleted(tmp_path, monkeypatch):
    key_env = "NSGABLACK_SHARED_PAYLOAD_TEST_HMAC_KEY"
    monkeypatch.setenv(key_env, "shared-payload-test-only-key")
    solver = _solver(
        snapshot_store_backend="file",
        snapshot_store_dir=str(tmp_path / "snapshots"),
        snapshot_store_key_prefix="shared-payload-test",
        snapshot_store_hmac_env_var=key_env,
    )
    assert solver.snapshot_store.backend == "file"
    batch, feedback, provenance = _record_event(solver)
    monkeypatch.setattr(solver, "export_evaluation_event_checkpoint_state", _forbid_reexport)

    identity = _publish_authority(solver, batch, feedback, provenance)
    _delete_event(solver)

    authority = solver.snapshot_store.read_verified_view(identity)
    assert authority.schema == POPULATION_SNAPSHOT_SCHEMA_V2
    _assert_complete_event(authority.data[LAST_EVALUATION_EVENT_KEY], batch, feedback)


def test_shared_partitioned_view_cannot_be_read_as_one_population():
    solver = _solver()
    batch, feedback, provenance = _record_event(solver)
    event = solver.snapshot_store.read_verified_view(_event_identity(solver))
    partition = PopulationPartition(
        partition_id="worker-a",
        population=batch.numeric_matrix,
        objectives=feedback.objectives,
        violations=feedback.violations,
        candidate_tokens=batch.candidate_tokens,
    )
    solver.restore_candidate_population_partitions_checkpoint_state({
        "schema": "nsgablack.candidate_population_partitions/v1",
        "authority_mode": "partitioned",
        "partitions": [{
            "partition": partition.as_dict(),
            "batch": batch.as_dict(),
            "provenance": [item.as_dict() for item in provenance],
        }],
    })

    assert solver.write_partitioned_population_snapshot()
    identity = solver.get_population_authority_identity().snapshot
    authority = solver.snapshot_store.read_verified_view(identity)

    assert population_snapshot_authority_mode(authority.data) == "partitioned"
    assert not {"population", "objectives", "constraint_violations"} & authority.data.keys()
    assert authority.data[LAST_EVALUATED_BATCH_KEY]["evaluation_event_envelope"] is event.data[EVALUATION_EVENT_KEY]
    validate_population_snapshot_v2(
        authority.data, snapshot_schema=authority.schema,
        expected_authority_mode="partitioned",
    )
    with pytest.raises(PartitionedPopulationSnapshotError):
        require_single_population_payload(authority.data)
