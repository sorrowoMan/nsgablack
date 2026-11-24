from __future__ import annotations

import numpy as np
import pytest

from blackbase.context import create_snapshot_store
from blackbase.resources import DataRef
from blackbase.types import CandidateBatch, Feedback
from nsgablack.core.evaluation_feedback import OptimizationFeedbackBatch
from nsgablack.core.state.pool_retention import PoolRetentionPolicy
from nsgablack.core.state.solution_pool import SolutionPool


def _pool(backend="memory", folder=None):
    return SolutionPool(
        create_snapshot_store(backend=backend, base_dir=None if folder is None else str(folder)),
        run_id="feedback-info-run",
    )


def _batch(tokens=("a", "b")):
    return CandidateBatch.from_candidates(
        [[float(index)] for index in range(len(tokens))], candidate_tokens=tokens
    )


def _feedback(infos):
    return OptimizationFeedbackBatch.from_feedback(
        [Feedback(objectives=[float(index)], info=info) for index, info in enumerate(infos)]
    )


def _retention_commit(pool):
    pool.begin_attempt()
    pool.stage_retention_step()
    pool.prepare_publication()
    pool.commit_publication()
    pool.collect_garbage()


@pytest.mark.parametrize("backend", ["memory", "file"])
def test_feedback_info_stays_detached_and_aligned_with_exact_ordered_refs(backend, tmp_path):
    pool = _pool(backend, tmp_path)
    original = {"child": {"identity": "first", "bindings": [{"receipt": "first-receipt"}]}}
    feedback = _feedback([original, {"child": {"identity": "second"}}])
    refs = pool.put(_batch(), stage="accepted", feedback=feedback)
    original["child"]["bindings"][0]["receipt"] = "mutated"
    reordered = pool.read_raw_feedback_info((refs[1], refs[0], refs[1]))
    assert [info["child"]["identity"] for info in reordered] == ["second", "first", "second"]
    assert reordered[1]["child"]["bindings"][0]["receipt"] == "first-receipt"
    reordered[1]["child"]["bindings"][0]["receipt"] = "changed-export"
    reordered[0]["child"]["identity"] = "changed-duplicate"
    assert reordered[2]["child"]["identity"] == "second"
    assert pool.read_raw_feedback_info(refs)[0]["child"]["bindings"][0]["receipt"] == "first-receipt"
    same_tokens = pool.put(_batch(), stage="accepted", feedback=_feedback([
        {"child": {"identity": "new-version"}}, {}]))
    assert pool.read_raw_feedback_info(refs[:1])[0]["child"]["identity"] == "first"
    assert pool.read_raw_feedback_info(same_tokens[:1])[0]["child"]["identity"] == "new-version"
    assert pool.read_raw_feedback_info(()) == ()


def test_feedback_info_uses_shared_reference_codec_without_copying_artifact_contents():
    pool = _pool()
    artifact = DataRef(uri="memory://child-summary", kind="result", checksum="sha256:" + "a" * 64)
    refs = pool.put(_batch(("a",)), stage="accepted", feedback=_feedback([
        {"summary_ref": artifact, "child_identity": {"run": "child-1"}}]))
    info = pool.read_raw_feedback_info(refs)[0]
    assert info["summary_ref"] == artifact
    assert info["child_identity"] == {"run": "child-1"}


@pytest.mark.parametrize("backend", ["memory", "file"])
def test_feedback_info_follows_publication_rollback_and_portable_checkpoint(backend, tmp_path):
    pool = _pool(backend, tmp_path / "source")
    refs = pool.put(_batch(), stage="accepted", feedback=_feedback([
        {"identity": "first"}, {"identity": "second"}]))
    baseline = pool.snapshot_step_state()
    pool.begin_attempt()
    pending = pool.put(_batch(("pending",)), stage="accepted", feedback=_feedback([
        {"identity": "uncommitted"}]))
    with pytest.raises(ValueError, match="uncommitted"):
        pool.read_raw_feedback_info(pending)
    assert pool.read_raw_feedback_info(pending, allow_pending=True)[0]["identity"] == "uncommitted"
    pool.prepare_publication()
    pool.restore_step_state(baseline)
    with pytest.raises(ValueError, match="unavailable"):
        pool.read_raw_feedback_info(pending, allow_pending=True)
    assert [info["identity"] for info in pool.read_raw_feedback_info(refs)] == ["first", "second"]

    pool.begin_attempt()
    committed = pool.put(_batch(("committed",)), stage="accepted", feedback=_feedback([
        {"identity": "committed"}]))
    publication = pool.prepare_publication()
    pool.commit_publication()
    same_store = SolutionPool(pool.snapshots)
    same_store.restore_publication(publication)
    assert same_store.read_raw_feedback_info(committed)[0]["identity"] == "committed"
    target = _pool(backend, tmp_path / "target")
    target.set_state(pool.get_state())
    assert target.read_raw_feedback_info(refs + committed) == pool.read_raw_feedback_info(refs + committed)


@pytest.mark.parametrize("backend", ["memory", "file"])
def test_feedback_info_retention_compaction_preserves_original_reference_rows(backend, tmp_path):
    pool = _pool(backend, tmp_path)
    pool.set_retention_policy(PoolRetentionPolicy(2, 1))
    refs = pool.put(_batch(), stage="accepted", feedback=_feedback([
        {"identity": "retired"}, {"identity": "retained"}]))
    pool.retain("unit", refs[1:])
    _retention_commit(pool)
    _retention_commit(pool)
    assert pool.select() == refs[1:]
    assert pool.select()[0].row == 1
    assert pool.read_raw_feedback_info(refs[1:])[0]["identity"] == "retained"
    np.testing.assert_array_equal(pool.read_raw_feedback(refs[1:])[0], [[1.]])
    with pytest.raises(ValueError, match="retired"):
        pool.read_raw_feedback_info(refs[:1])


def test_old_snapshot_without_feedback_info_reads_empty_mapping_and_checkpoints(monkeypatch):
    store = create_snapshot_store(backend="memory")
    original_write = store.write

    def legacy_write(data, **kwargs):
        if isinstance(data, dict) and data.get("raw_feedback") is not None:
            data = {**data, "raw_feedback": {
                key: value for key, value in data["raw_feedback"].items() if key != "info"}}
        return original_write(data, **kwargs)

    monkeypatch.setattr(store, "write", legacy_write)
    source = SolutionPool(store, run_id="old-info-run")
    refs = source.put(_batch(), stage="accepted", feedback=_feedback([{}, {}]))
    unevaluated = source.put(_batch(("initial",)))
    assert source.read_raw_feedback_info(refs + unevaluated) == ({}, {}, {})
    target = _pool()
    target.set_state(source.get_state())
    assert target.read_raw_feedback_info(refs + unevaluated) == ({}, {}, {})
