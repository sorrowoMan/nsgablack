"""Retire unused rows without deleting live identities or retained restore roots."""
import copy

import numpy as np
import pytest
from blackbase.context import SnapshotIdentity, create_snapshot_store

from nsgablack.core import PoolRetentionPolicy, SolutionPool
from tests.test_solution_pool import batch
from tests.test_pool_search_adapter import make_solver


def make_pool(*, idle_steps=2, retained_publications=1):
    value = SolutionPool(create_snapshot_store(backend="memory"), run_id="retention-run")
    value.set_retention_policy(PoolRetentionPolicy(idle_steps, retained_publications))
    return value


def commit_retention(pool):
    pool.begin_attempt()
    pool.stage_retention_step()
    pool.prepare_publication()
    pool.commit_publication()
    return pool.collect_garbage()


def test_two_unit_owners_protect_same_candidate_until_both_release():
    p = make_pool()
    refs = p.put(batch(), stage="accepted")
    p.retain("a", refs[:1])
    p.retain("b", refs[:1])
    commit_retention(p)
    p.release("a")
    commit_retention(p)
    assert p.select() == refs[:1]
    assert p.read(refs[:1]).candidate_tokens == ("a",)
    p.release("b")
    commit_retention(p)
    assert p.select() == refs[:1]  # One committed step of grace.
    commit_retention(p)
    assert p.select() == ()


@pytest.mark.parametrize("backend", ["memory", "file"])
def test_compaction_frees_unused_row_values_without_reindexing_live_refs(backend, tmp_path):
    p = SolutionPool(create_snapshot_store(backend=backend, base_dir=str(tmp_path)))
    p.set_retention_policy(PoolRetentionPolicy(2, 1))
    refs = p.put(batch((1., 2., 3.), ("a", "b", "c")), stage="accepted")
    old = p._record(refs[0]).snapshot
    p.retain("unit", refs[1:2])
    commit_retention(p)
    result = commit_retention(p)
    assert result["deleted"] >= 1
    assert p.snapshots.read(old.key) is None
    assert p.select() == refs[1:2]
    assert p.select()[0].row == 1
    value = p.read(refs[1:2])
    np.testing.assert_array_equal(value.numeric_matrix, [[2.]])
    assert value.semantic_states[0].metadata["label"] == "b"
    assert p._payload(p._record(refs[1]))[1].candidate_tokens == ("b",)
    assert p._record(refs[1]).tokens == ("b",)  # Retired identity rows leave the index too.
    with pytest.raises(ValueError, match="retired"):
        p.read(refs[:1])


def test_reads_and_observation_do_not_extend_idle_lifetime():
    p = make_pool()
    refs = p.put(batch(), stage="accepted")
    commit_retention(p)
    for _ in range(3):
        p.read(refs)
        p.select()
    commit_retention(p)
    assert p.select() == ()


def test_pending_inputs_pin_rows_and_consumed_inputs_stop_retaining_values():
    p = make_pool(idle_steps=1)
    refs = p.put(batch(), stage="accepted")
    key = p.bind_input(refs)
    commit_retention(p)
    assert p.select() == refs
    p.begin_attempt()
    assert p.take_input(key) == refs[0]
    p.settle_input(key, 1, (0,))
    p.stage_retention_step()
    p.prepare_publication()
    p.commit_publication()
    p.collect_garbage()
    assert p.input_remaining(key) == 1
    assert p.select() == refs[1:]
    assert p.take_input(key) == refs[1]


def test_retention_rollback_restores_rows_clock_and_roots_without_deleting_storage():
    p = make_pool()
    refs = p.put(batch(), stage="accepted")
    p.retain("a", refs)
    commit_retention(p)
    saved = p.snapshot_step_state()
    old = p._record(refs[0]).snapshot
    p.begin_attempt()
    p.release("a")
    p.stage_retention_step()
    p.prepare_publication()
    with pytest.raises(RuntimeError, match="committed"):
        p.collect_garbage()
    p.restore_step_state(saved)
    assert p.select() == refs and p._retention_step == 1
    assert p.snapshots.read_verified(old)


def test_historical_publication_pin_keeps_full_value_closure_until_unpinned():
    p = make_pool(idle_steps=1)
    refs = p.put(batch(), stage="accepted")
    p.retain("unit", refs)
    commit_retention(p)
    old_value = p._record(refs[0]).snapshot
    root = p.pin_publication("checkpoint")
    p.release("unit")
    commit_retention(p)
    assert p.select() == () and p.snapshots.read(old_value.key) is not None
    view = SolutionPool(p.snapshots)
    view.restore_publication(root)
    np.testing.assert_array_equal(view.read(refs).numeric_matrix, [[1.], [2.]])
    p.unpin_publication("checkpoint", root)
    p.collect_garbage()
    assert p.snapshots.read(old_value.key) is None
    with pytest.raises(KeyError):
        view.restore_publication(root)


def test_portable_checkpoint_keeps_values_after_source_gc_and_compacted_rows_restore():
    p = make_pool(idle_steps=1)
    refs = p.put(batch(), stage="accepted")
    p.retain("unit", refs)
    commit_retention(p)
    old_checkpoint = copy.deepcopy(p.get_state())
    p.retain("unit", refs[1:])
    commit_retention(p)
    compacted_checkpoint = p.get_state()
    fresh = SolutionPool(create_snapshot_store(backend="memory"))
    fresh.set_state(old_checkpoint)
    assert fresh.read(refs).candidate_tokens == ("a", "b")
    fresh.set_state(compacted_checkpoint)
    assert fresh.select() == refs[1:]
    assert fresh.read(refs[1:]).candidate_tokens == ("b",)
    assert fresh.retention_policy == p.retention_policy


def test_delete_failure_is_retryable_and_does_not_reverse_committed_index(monkeypatch):
    p = make_pool(idle_steps=1)
    refs = p.put(batch(), stage="accepted")
    p.retain("unit", refs)
    commit_retention(p)
    old = p._record(refs[0]).snapshot
    original = p.snapshots.delete
    def failing(key):
        if key == old.key:
            raise OSError("storage unavailable")
        return original(key)
    monkeypatch.setattr(p.snapshots, "delete", failing)
    p.release("unit")
    report = commit_retention(p)
    assert p.select() == () and report["errors"]
    assert old.key in p._garbage
    monkeypatch.setattr(p.snapshots, "delete", original)
    assert not p.collect_garbage()["errors"]
    assert p.snapshots.read(old.key) is None


def test_pool_search_runs_and_restores_with_retention_and_private_unit_roots():
    from nsgablack.plugins import CheckpointResumePlugin
    source, producer, left, right = make_solver(count=2, batch_size=3)
    source.set_solution_pool_retention(PoolRetentionPolicy(idle_steps=1, retained_publications=2))
    for _ in range(7):
        assert source.step().committed
    assert len(left.population) == len(right.population) == 2
    assert source.solution_pool.select()
    writer = CheckpointResumePlugin()
    writer.attach(source)
    payload = writer._build_payload(solver=source, reason="pool-retention")
    target, *_ = make_solver(count=2, batch_size=3)
    reader = CheckpointResumePlugin()
    reader.attach(target)
    reader._restore_payload(solver=target, payload=payload)
    assert target.solution_pool.retention_policy == source.solution_pool.retention_policy
    assert target.step().committed


@pytest.mark.parametrize("values", [(0, 1), (1, 0), (True, 2)])
def test_policy_rejects_invalid_limits(values):
    with pytest.raises(ValueError):
        PoolRetentionPolicy(*values)


def test_failed_compaction_and_prepared_manifest_are_collected_after_rollback():
    p = make_pool(idle_steps=1)
    refs = p.put(batch(), stage="accepted")
    p.retain("unit", refs)
    commit_retention(p)
    baseline = p.snapshot_step_state()
    original = p._record(refs[0]).snapshot
    p.begin_attempt()
    p.retain("unit", refs[1:])
    p.stage_retention_step()
    compact = p._record(refs[1]).snapshot
    prepared = p.prepare_publication()
    p.restore_step_state(baseline)
    report = p.collect_garbage()
    assert not report["errors"]
    assert p.snapshots.read(compact.key) is None
    assert p.snapshots.read(prepared["key"]) is None
    assert p.snapshots.read_verified(original)
    assert p.select() == refs


def test_same_named_owner_pins_shared_values_independently_per_publication():
    p = make_pool(idle_steps=1)
    refs = p.put(batch(), stage="accepted")
    p.retain("unit", refs)
    commit_retention(p)
    first = p.pin_publication("saved")
    value = p._record(refs[0]).snapshot
    commit_retention(p)
    second = p.pin_publication("saved")
    p.unpin_publication("saved", first)
    p.release("unit")
    commit_retention(p)
    assert p.snapshots.read(value.key) is not None
    view = SolutionPool(p.snapshots)
    view.restore_publication(second)
    assert view.select() == refs
    p.unpin_publication("saved", second)
    p.collect_garbage()
    assert p.snapshots.read(value.key) is None


def test_unmigrated_adapter_is_rejected_before_enabling_and_reported_by_doctor():
    from nsgablack.adapters import AlgorithmAdapter
    from nsgablack.utils.runtime_contracts import inspect_runtime_contracts
    solver, *_ = make_solver(count=2, batch_size=3)
    class Undeclared(AlgorithmAdapter):
        def propose(self, control, context):
            return ()
        def update(self, control, candidates, feedback, context):
            pass
    solver.adapter = Undeclared(name="undeclared")
    with pytest.raises(ValueError, match="get_solution_pool_roots"):
        solver.set_solution_pool_retention(PoolRetentionPolicy())
    assert solver.solution_pool.retention_policy is None
    solver.solution_pool.set_retention_policy(PoolRetentionPolicy())
    assert "solution-pool-retention-contract-invalid" in dict(inspect_runtime_contracts(solver))


def test_solver_publication_failure_restores_unit_pool_and_retention_clock(monkeypatch):
    solver, _, left, right = make_solver(count=2, batch_size=3)
    solver.set_solution_pool_retention(PoolRetentionPolicy(idle_steps=1))
    for _ in range(3):
        assert solver.step().committed
    pool = solver.solution_pool
    before_refs, before_clock = pool.select(), pool._retention_step
    tokens = (left.get_population_candidate_tokens(), right.get_population_candidate_tokens())
    original = pool.prepare_publication
    def fail_after_prepare():
        original()
        raise OSError("publication unavailable")
    monkeypatch.setattr(pool, "prepare_publication", fail_after_prepare)
    with pytest.raises(OSError, match="publication unavailable"):
        solver.step()
    assert pool.select() == before_refs and pool._retention_step == before_clock
    assert (left.get_population_candidate_tokens(), right.get_population_candidate_tokens()) == tokens
    assert pool._garbage
    monkeypatch.setattr(pool, "prepare_publication", original)
    assert solver.step().committed


def test_uncertain_authority_commit_keeps_pool_value_closure_until_reconciled(monkeypatch):
    solver, *_ = make_solver(count=2, batch_size=3)
    solver.set_solution_pool_retention(PoolRetentionPolicy(idle_steps=1))
    for _ in range(3):
        assert solver.step().committed
    original = solver.commit_snapshot_step_transaction
    def lose_acknowledgement():
        original()
        raise OSError("Authority acknowledgement lost")
    monkeypatch.setattr(solver, "commit_snapshot_step_transaction", lose_acknowledgement)
    with pytest.raises(OSError, match="acknowledgement lost"):
        solver.step()
    record = solver.evaluation_evidence_journal.get(solver._last_evaluation_event_id)
    assert record.phase == "decision_ready"
    destination = solver.snapshot_store.read(record.disposition["authority_snapshot_key"])
    root = destination.data["solution_pool_ref"]
    pool = solver.solution_pool
    pool.collect_garbage()
    assert solver.snapshot_store.read(root["key"]).pinned
    view = SolutionPool(solver.snapshot_store)
    view.restore_publication(root)
    assert view.select()
    report = solver.reconcile_evaluation_evidence(record.run_id)
    assert report["settled_count"] == 1
    assert pool.publication_ref() == root
    assert not pool.collect_garbage()["errors"]
    assert not solver.snapshot_store.read(root["key"]).pinned


def test_snapshot_policy_and_prepared_index_are_detached_from_live_state():
    p = make_pool()
    refs = p.put(batch(), stage="accepted")
    p.retain("unit", refs)
    state = p.snapshot_step_state()
    state["index"]["retention"]["policy"]["idle_steps"] = 9
    assert p.retention_policy.idle_steps == 2
    p.begin_attempt()
    p.stage_retention_step()
    p.prepare_publication()
    state = p.snapshot_step_state()
    state["prepared_index"]["records"][0]["region"] = "changed"
    p.commit_publication()
    assert p.select() == refs
