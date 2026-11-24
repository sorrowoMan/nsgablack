"""Typed numeric storage preserves every candidate/reference/digest contract."""
import copy
import json

import numpy as np
import pytest

from blackbase.context import create_snapshot_store
from blackbase.context import snapshot_content_bytes, LEGACY_SNAPSHOT_DIGEST_CODEC, SNAPSHOT_DIGEST_CODEC
from blackbase.types import CandidateBatch, UnknownState
from nsgablack.core.evaluation_feedback import OptimizationFeedbackBatch
from nsgablack.core.state import solution_pool as module
from nsgablack.core.state.pool_retention import PoolRetentionPolicy
from nsgablack.core.state.solution_pool import SolutionPool
from nsgablack.core.state.candidate_batch_payload import candidate_batch_snapshot_payload


def candidate_batch():
    return CandidateBatch.from_candidates(
        [UnknownState([2.0, 3.0], {"label": "first", "layout": {"shape": [2]}}),
         UnknownState([2.0, 3.0], {"label": "second", "layout": {"shape": [2]}})],
        candidate_tokens=("a", "b"),
    )


@pytest.mark.parametrize("codec", [LEGACY_SNAPSHOT_DIGEST_CODEC, SNAPSHOT_DIGEST_CODEC])
def test_typed_payload_preserves_exact_preimage_without_building_numeric_lists(codec, monkeypatch):
    batch = candidate_batch()
    previous = batch.as_dict()
    previous["numeric_matrix"] = np.array(batch.numeric_matrix, copy=True)
    for state, payload in zip(batch.semantic_states, previous["semantic_states"], strict=True):
        payload["values"] = state.as_array()
    expected = snapshot_content_bytes("test/v1", previous, digest_codec=codec)

    def forbidden(*args, **kwargs):
        pytest.fail("Snapshot encoding expanded numeric data through as_dict")

    monkeypatch.setattr(CandidateBatch, "as_dict", forbidden)
    observed = candidate_batch_snapshot_payload(batch)
    assert snapshot_content_bytes("test/v1", observed, digest_codec=codec) == expected


def make_pool(backend, folder):
    return SolutionPool(create_snapshot_store(backend=backend, base_dir=str(folder)), run_id="typed-pool")


def payload(pool, ref):
    return pool.snapshots.read_verified(pool._record(ref).snapshot).data


def commit_retention(pool):
    pool.begin_attempt()
    pool.stage_retention_step()
    pool.prepare_publication()
    pool.commit_publication()
    return pool.collect_garbage()


@pytest.mark.parametrize("backend", ["memory", "file"])
def test_dense_values_use_arrays_but_public_json_and_equal_candidate_identities_are_unchanged(backend, tmp_path):
    source = make_pool(backend, tmp_path)
    batch = candidate_batch()
    first = source.put(batch, stage="accepted")
    second = source.put(batch, stage="accepted")
    assert first != second
    assert first[0].record_id != second[0].record_id
    assert first[0].candidate_token == second[0].candidate_token == "a"
    assert first[0].candidate_token != first[1].candidate_token
    observed = payload(source, first[0])["batch"]
    assert isinstance(observed["numeric_matrix"], np.ndarray)
    assert all(isinstance(row["values"], np.ndarray) for row in observed["semantic_states"])
    numeric = observed["numeric_matrix"].copy()
    observed["numeric_matrix"][:] = -1
    observed["semantic_states"][0]["values"][:] = -1
    restored = source.read(first)
    np.testing.assert_array_equal(restored.numeric_matrix, numeric)
    np.testing.assert_array_equal(batch.numeric_matrix, numeric)
    assert [state.metadata["label"] for state in restored.semantic_states] == ["first", "second"]
    assert isinstance(restored.as_dict()["numeric_matrix"], list)
    assert isinstance(restored.as_dict()["semantic_states"][0]["values"], list)
    json.dumps(restored.as_dict(), allow_nan=False)


@pytest.mark.parametrize("backend", ["memory", "file"])
def test_cross_store_checkpoint_preserves_typed_digest_and_raw_feedback(backend, tmp_path):
    source = make_pool(backend, tmp_path / "source")
    refs = source.put(candidate_batch(), stage="accepted",
                      feedback=OptimizationFeedbackBatch.from_arrays([[1.0, 2.0], [3.0, 4.0]], [0.0, 2.0]))
    state = source.get_state()
    original = source._record(refs[0]).snapshot
    target = make_pool(backend, tmp_path / "target")
    target.set_state(state)
    restored = target._record(refs[0]).snapshot
    assert restored.store_scope != original.store_scope
    assert restored.content_digest == original.content_digest
    assert restored.key != original.key
    assert target.select() == refs
    np.testing.assert_array_equal(target.read(refs).numeric_matrix, candidate_batch().numeric_matrix)
    objectives, violations = target.read_raw_feedback(refs)
    np.testing.assert_array_equal(objectives, [[1.0, 2.0], [3.0, 4.0]])
    np.testing.assert_array_equal(violations, [0.0, 2.0])


@pytest.mark.parametrize("view", ["numeric", "semantic"])
def test_tampering_either_numeric_view_still_fails_digest_without_replacing_state(view, tmp_path):
    source = make_pool("memory", tmp_path / "source")
    refs = source.put(candidate_batch(), stage="accepted")
    target = make_pool("memory", tmp_path / "target")
    target.set_state(source.get_state())
    damaged = copy.deepcopy(source.get_state())
    batch = damaged["payloads"][refs[0].record_id]["batch"]
    if view == "numeric":
        batch["numeric_matrix"][0, 0] += 100.0
    else:
        batch["semantic_states"][0]["values"][0] += 100.0
    with pytest.raises(ValueError, match="digest"):
        target.set_state(damaged)
    assert target.select() == refs
    np.testing.assert_array_equal(target.read(refs).numeric_matrix, candidate_batch().numeric_matrix)


def test_old_list_checkpoint_restores_without_reencoding_its_identity(monkeypatch, tmp_path):
    source = make_pool("memory", tmp_path / "old")
    with monkeypatch.context() as legacy:
        legacy.setattr(module, "candidate_batch_snapshot_payload", lambda batch: batch.as_dict())
        refs = source.put(candidate_batch(), stage="accepted")
    old_identity = source._record(refs[0]).snapshot
    state = source.get_state()
    assert isinstance(state["payloads"][refs[0].record_id]["batch"]["numeric_matrix"], list)
    target = make_pool("memory", tmp_path / "new")
    target.set_state(state)
    assert target._record(refs[0]).snapshot.content_digest == old_identity.content_digest
    assert target.select() == refs
    np.testing.assert_array_equal(target.read(refs).numeric_matrix, candidate_batch().numeric_matrix)


@pytest.mark.parametrize("backend", ["memory", "file"])
def test_retention_compaction_uses_arrays_and_rollback_restores_original_rows(backend, tmp_path):
    pool = make_pool(backend, tmp_path)
    pool.set_retention_policy(PoolRetentionPolicy(2, 1))
    refs = pool.put(candidate_batch(), stage="accepted")
    pool.retain("unit", refs[1:])
    commit_retention(pool)
    original = pool._record(refs[0]).snapshot
    baseline = pool.snapshot_step_state()
    pool.begin_attempt()
    pool.stage_retention_step()
    assert isinstance(payload(pool, refs[1])["batch"]["numeric_matrix"], np.ndarray)
    assert pool._record(refs[1]).available_rows == (1,)
    pool.prepare_publication()
    pool.restore_step_state(baseline)
    assert pool.select() == refs
    assert pool._record(refs[0]).snapshot == original
    commit_retention(pool)
    assert pool.select() == refs[1:]
    assert pool.select()[0].row == 1
    compacted = payload(pool, refs[1])["batch"]
    assert isinstance(compacted["numeric_matrix"], np.ndarray)
    np.testing.assert_array_equal(compacted["numeric_matrix"], [[2.0, 3.0]])
    assert pool.read(refs[1:]).semantic_states[0].metadata["label"] == "second"
