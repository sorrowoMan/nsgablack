"""Partition remains a read-only choice inside real publication and restore."""
from __future__ import annotations

import copy

import numpy as np
import pytest
from blackbase.context import SnapshotIdentity
from blackbase.types import CandidateBatch

from nsgablack.adapters import ChangeResult, NSGA2Adapter, partition
from nsgablack.adapters.change_batch import ChangeBatchResult
from nsgablack.context_keys import KEY_SOLUTION_INPUT_REF
from nsgablack.core import BlackBoxProblem, ComposableSolver
from nsgablack.plugins import CheckpointResumeConfig, CheckpointResumePlugin
from nsgablack.representation import ClipRepair, RepresentationPipeline, UniformInitializer


class PartitionSphere(BlackBoxProblem):
    def __init__(self):
        super().__init__(dimension=1, objectives=["minimize"], bounds=[(-50., 50.)])
        self.calls = []

    def evaluate(self, candidate):
        value = np.array(candidate, dtype=float, copy=True)
        self.calls.append(value)
        return [float(np.dot(value, value))]


def paired_changes(request, *, rng):
    a, b = request.parents[:2]
    shift = rng.uniform(.05, .15, size=a.shape)
    return ChangeBatchResult((ChangeResult((a + b) / 2. - shift),
                              ChangeResult((a + b) / 2. - 2. * shift)))


def choose_four(pool):
    return pool.sort(lambda rows: rows.objectives[:, 0]).take(range(4))


def raw_key(pool):
    return pool.raw_feedback()[0][:, 0]


def choose_last_duplicate(pool):
    refs = pool.refs
    index = next(index for index in range(len(refs) - 1, -1, -1) if refs.count(refs[index]) > 1)
    return pool.take((index,))


def choose_all(pool):
    return pool.all()


def washed_duplicate(pool):
    # Local occurrence numbers may distinguish the two copies, but cannot
    # turn outer coordinate zero into two legitimate survivor positions.
    selected, _ = partition(pool.take((0, 1, 0, 2)), by=choose_all)
    return selected


def split_accepted(request, *, rng):
    offered = request.accepted.take((2, 0, 2, 1)).sort(raw_key)
    selected, remaining = partition(offered, by=choose_last_duplicate, rng=rng)
    return (request.pool.replace_members("elite", selected.refs),
            request.pool.replace_members("reserve", remaining.refs))


def make_solver(*, selector=choose_four, setup=True):
    adapter = NSGA2Adapter(population_size=4, offspring_size=4, change=paired_changes,
                          selector=selector, pool_maintenance=split_accepted)
    solver = ComposableSolver(PartitionSphere(), adapter=adapter,
        representation_pipeline=RepresentationPipeline(initializer=UniformInitializer(4., 5.),
                                                       repair=ClipRepair(-50., 50.)))
    solver.set_random_seed(719)
    if setup:
        solver.setup()
        solver.solution_pool.create_subpool("elite")
        solver.solution_pool.create_subpool("reserve")
    return solver


def assert_manifest_members(solver):
    pool = solver.solution_pool
    manifest_ref = pool.publication_ref()
    manifest = pool.snapshots.read_verified(SnapshotIdentity.from_dict(manifest_ref)).data
    for name in ("elite", "reserve"):
        assert manifest["retention"]["owners"][f"subpool/{name}"] == [
            ref.as_dict() for ref in pool.subpool_refs(name)]
        assert manifest["subpool_metadata"][name] == pool.subpool_metadata(name)
    authority = solver.snapshot_store.read_verified(solver.get_population_authority_identity().snapshot).data
    assert authority["solution_pool_ref"] == manifest_ref


def expected_partition(solver, refs):
    input_refs = (refs[2], refs[0], refs[2], refs[1])
    values = solver.solution_pool.read_raw_feedback(input_refs)[0][:, 0]
    indices = np.argsort(values, kind="stable")
    ordered = tuple(input_refs[index] for index in indices)
    chosen = max(index for index, ref in enumerate(ordered) if ordered.count(ref) > 1)
    return (ordered[chosen],), tuple(ref for index, ref in enumerate(ordered) if index != chosen)


def test_real_updates_partition_sorted_accepted_occurrences_without_deleting_other_slots():
    solver = make_solver()
    initial_identity = solver.solution_pool.subpool_descriptor("elite")
    for _ in range(2):
        before = solver.solution_pool.select(stage="accepted")
        assert solver.step().committed
        accepted = solver.solution_pool.select(stage="accepted")[len(before):]
        assert len(accepted) == 4
        selected, remaining = expected_partition(solver, accepted)
        assert solver.solution_pool.subpool_refs("elite") == selected
        assert solver.solution_pool.subpool_refs("reserve") == remaining
        assert selected[0] in remaining  # Same reference, different input occurrence.
        assert len(selected) + len(remaining) == 4
        assert solver.solution_pool.subpool_descriptor("elite")["view_id"] == initial_identity["view_id"]
        assert_manifest_members(solver)
    assert solver.evaluation_count == 8
    assert len(solver.solution_pool.select(stage="accepted")) == 8


def test_rebased_duplicate_selection_fails_real_step_and_restores_input_cursor(monkeypatch):
    solver = make_solver(selector=washed_duplicate)
    pool = solver.solution_pool
    seeds = solver.store_solutions(CandidateBatch.from_candidates([[1.], [2.], [3.], [4.]],
        candidate_tokens=("seed-a", "seed-b", "seed-c", "seed-d")))
    cursor = pool.bind_input(seeds)
    ordinary_context = solver.build_context

    def intake_context(*args, **kwargs):
        context = ordinary_context(*args, **kwargs)
        context[KEY_SOLUTION_INPUT_REF] = cursor
        return context

    monkeypatch.setattr(solver, "build_context", intake_context)
    descriptors = {name: pool.subpool_descriptor(name) for name in ("elite", "reserve")}
    with pytest.raises(ValueError, match="repeat|distinct"):
        solver.step()
    assert pool.input_remaining(cursor) == 4
    assert pool.select(stage="initial") == seeds
    assert pool.select(stage="accepted") == ()
    assert solver.adapter.algorithm_unit is None
    assert pool.publication_ref() is None
    assert solver.get_population_authority_identity() is None
    for name in descriptors:
        assert pool.subpool_refs(name) == ()
        assert pool.subpool_descriptor(name) == descriptors[name]
    assert solver.evaluation_count == 4  # Real work survives rollback.

    solver.adapter.set_selector(choose_four)
    assert solver.step().committed
    assert pool.input_remaining(cursor) == 0
    np.testing.assert_array_equal(solver.problem.calls[:4], solver.problem.calls[4:])
    assert_manifest_members(solver)


def test_formal_checkpoint_preserves_partition_member_order_versions_and_continuation(tmp_path, monkeypatch):
    monkeypatch.setenv("NSGABLACK_CHECKPOINT_HMAC_KEY", "partition-formal-restore-key")
    source = make_solver()
    assert source.step().committed
    assert source.step().committed
    pool = source.solution_pool
    saved_refs = pool.select(stage=None)
    saved_members = {name: pool.subpool_refs(name) for name in ("elite", "reserve")}
    saved_descriptors = {name: pool.subpool_descriptor(name) for name in saved_members}
    saved_state = copy.deepcopy(source.adapter.get_state())
    config = CheckpointResumeConfig(checkpoint_dir=str(tmp_path), save_on_finish=False, strict=True)
    writer = CheckpointResumePlugin(config=config)
    source.add_plugin(writer)
    checkpoint = writer.save_checkpoint(reason="partition-members")
    assert checkpoint is not None

    restored = make_solver(setup=False)

    def never_reinitialize(*args, **kwargs):
        raise AssertionError("restoring existing partition members must not regenerate seeds")

    monkeypatch.setattr(restored.representation_pipeline.initializer, "initialize", never_reinitialize)
    reader = CheckpointResumePlugin(config=config)
    restored.add_plugin(reader)
    assert reader.resume(str(checkpoint))
    restored.run(max_steps=0)
    assert restored.problem.calls == []
    assert restored.solution_pool.select(stage=None) == saved_refs
    assert restored.adapter.get_state() == saved_state
    for name in saved_members:
        assert restored.solution_pool.subpool_refs(name) == saved_members[name]
        assert restored.solution_pool.subpool_descriptor(name) == saved_descriptors[name]
        np.testing.assert_array_equal(restored.read_solutions(saved_members[name]).numeric_matrix,
                                      source.read_solutions(saved_members[name]).numeric_matrix)

    previous_calls = len(source.problem.calls)
    assert source.step().committed
    assert restored.step().committed
    np.testing.assert_array_equal(restored.problem.calls, source.problem.calls[previous_calls:])
    assert restored.adapter._rng.bit_generator.state == source.adapter._rng.bit_generator.state
    for name in saved_members:
        left = restored.solution_pool.subpool_refs(name)
        right = source.solution_pool.subpool_refs(name)
        np.testing.assert_array_equal(restored.read_solutions(left).numeric_matrix,
                                      source.read_solutions(right).numeric_matrix)
        assert restored.solution_pool.subpool_descriptor(name) == source.solution_pool.subpool_descriptor(name)
    assert_manifest_members(restored)
