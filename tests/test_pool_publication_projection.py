"""Reuse the verified publication index without caching stores or wire trust."""
import copy
from dataclasses import replace

import numpy as np
import pytest
from blackbase.context import SnapshotIdentity, create_snapshot_store

from nsgablack.core.state.solution_pool import SolutionPool, _Record
from tests.test_solution_pool import batch


def count_record_decodes(monkeypatch):
    decoded = []
    original = _Record.from_dict.__func__

    def counted(cls, value):
        decoded.append(value["record_id"])
        return original(cls, value)

    monkeypatch.setattr(_Record, "from_dict", classmethod(counted))
    return decoded


@pytest.mark.parametrize("backend", ["memory", "file"])
def test_prepare_commit_decodes_once_and_matches_verified_manifest(backend, tmp_path, monkeypatch):
    pool = SolutionPool(create_snapshot_store(backend=backend, base_dir=str(tmp_path)))
    first = pool.put(batch(), stage="accepted")
    pool.bind_input((first[1], first[0], first[1]))
    pool.create_subpool("elite", first[1:])
    pool.begin_attempt()
    second = pool.put(batch((3.,), ("c",)), stage="accepted")
    pool.publish_subpool_view("final", (second[0], first[0]), created_by=("ga",))
    draft = pool.put(batch((9.,), ("draft",)), stage="mutation")
    decoded = count_record_decodes(monkeypatch)

    manifest = pool.prepare_publication()
    durable = pool.snapshots.read_verified(SnapshotIdentity.from_dict(manifest)).data
    expected_ids = [r["record_id"] for r in durable["records"]]
    assert decoded == expected_ids and len(expected_ids) == 2
    assert pool.select() == first
    assert pool.subpool_refs("final") == ()

    snapshot = pool.snapshot_step_state()
    assert set(snapshot) == {"index", "manifest", "prepared", "in_attempt",
                             "prepared_index", "retention_staged"}
    # The transaction snapshot retains only the existing wire representation.
    assert snapshot["prepared_index"] == durable
    snapshot["prepared_index"]["records"][0]["source"] = "detached"
    pool.commit_publication()
    assert decoded == expected_ids  # commit constructs zero additional Records.
    assert pool._index_state() == durable
    assert pool.publication_ref() == manifest
    assert pool._prepared_projection is None
    assert pool.select() == first + second
    assert pool.subpool_refs("final") == (second[0], first[0])
    np.testing.assert_array_equal(pool.read(first + second).numeric_matrix, [[1.], [2.], [3.]])
    with pytest.raises(ValueError, match="unavailable"):
        pool.read(draft, allow_pending=True)


def test_rollback_discards_projection_before_a_different_publication():
    pool = SolutionPool(create_snapshot_store(backend="memory"))
    first = pool.put(batch(), stage="accepted")
    baseline = pool.snapshot_step_state()
    pool.begin_attempt()
    discarded = pool.put(batch((9.,), ("discarded",)), stage="accepted")
    old_manifest = pool.prepare_publication()
    old_projection = pool._prepared_projection
    pool.restore_step_state(baseline)
    assert pool._prepared_projection is None
    with pytest.raises(RuntimeError, match="not prepared"):
        pool.commit_publication()

    pool.begin_attempt()
    accepted = pool.put(batch((4.,), ("later",)), stage="accepted")
    manifest = pool.prepare_publication()
    assert manifest != old_manifest and pool._prepared_projection is not old_projection
    pool.commit_publication()
    assert pool.select() == first + accepted
    with pytest.raises(ValueError, match="unavailable"):
        pool.read(discarded, allow_pending=True)


def test_restored_prepared_snapshot_rebuilds_against_durable_manifest(monkeypatch):
    pool = SolutionPool(create_snapshot_store(backend="memory"))
    pool.begin_attempt()
    refs = pool.put(batch(), stage="accepted")
    manifest = pool.prepare_publication()
    saved = pool.snapshot_step_state()
    pool.restore_step_state(saved)
    assert pool._prepared_projection is None
    decoded = count_record_decodes(monkeypatch)
    verified = []
    original_read = pool.snapshots.read_verified

    def counted(identity):
        verified.append(identity)
        return original_read(identity)

    monkeypatch.setattr(pool.snapshots, "read_verified", counted)
    pool.commit_publication()
    assert decoded == [refs[0].record_id]
    assert verified == [SnapshotIdentity.from_dict(manifest)]
    assert pool.select() == refs and pool.publication_ref() == manifest


@pytest.mark.parametrize("corruption", ["index", "scope", "digest"])
def test_restored_prepared_snapshot_cannot_diverge_from_manifest(corruption):
    pool = SolutionPool(create_snapshot_store(backend="memory"))
    pool.begin_attempt()
    refs = pool.put(batch(), stage="accepted")
    pool.prepare_publication()
    saved = copy.deepcopy(pool.snapshot_step_state())
    if corruption == "index":
        saved["prepared_index"]["records"][0]["region"] = "different"
    elif corruption == "scope":
        saved["prepared"] = replace(saved["prepared"], store_scope="another-store")
    else:
        saved["prepared"] = replace(saved["prepared"], content_digest="sha256:" + "0" * 64)
    pool.restore_step_state(saved)
    with pytest.raises(ValueError):
        pool.commit_publication()
    assert pool._prepared_projection is None
    assert pool.select() == ()
    assert pool.read(refs, allow_pending=True).candidate_tokens == ("a", "b")


def test_projection_contains_only_owned_index_data():
    from nsgablack.core.state.pool_retention import PoolRetentionPolicy
    from nsgablack.core.state.solution_pool import SolutionRef, SolutionStamp

    pool = SolutionPool(create_snapshot_store(backend="memory"))
    pool.set_retention_policy(PoolRetentionPolicy())
    refs = pool.put(batch(), stage="accepted")
    pool.retain("unit", refs)
    pool.begin_attempt()
    pool.prepare_publication()

    def check(value):
        if isinstance(value, dict):
            for key, item in value.items():
                check(key)
                check(item)
        elif isinstance(value, (list, tuple)):
            for item in value:
                check(item)
        else:
            assert value is None or type(value) in {
                str, int, bool, SnapshotIdentity, SolutionRef, SolutionStamp,
                _Record, PoolRetentionPolicy}

    check(pool._prepared_projection)
