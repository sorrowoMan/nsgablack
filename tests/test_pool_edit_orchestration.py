"""Ordinary functions maintain named collections inside real step transactions."""
from __future__ import annotations

import copy
from functools import partial

import numpy as np
import pytest
from blackbase.context import SnapshotIdentity
from blackbase.contracts import BatchDisposition

from nsgablack.adapters import ChangeResult, PoolEdit, PoolOutput
from nsgablack.adapters.change_access import scoped_change_access
from nsgablack.plugins import CheckpointResumeConfig, CheckpointResumePlugin
from nsgablack.core.control_plane import BudgetController
from nsgablack.core.state.solution_pool import SolutionRef
from .test_pool_change_orchestration import make_solver, add_source


def elite_key(selection):
    objectives, violations = selection.raw_feedback()
    return np.column_stack((violations > 0., np.maximum(violations, 0.), objectives.sum(axis=1)))


def maintain_elite(request, *, rng):
    kept = request.pool.subpool("elite").merge(
        request.pool.main(stage="accepted")).top(2, key=elite_key)
    edit = request.pool.replace_members("elite", kept.refs)
    child = request.candidate - .2 + rng.uniform(-.01, .01, request.candidate.shape)
    return ChangeResult(child, outputs=(PoolOutput("offspring", create=True),), edits=(edit,))


def bare_change(request, *, rng):
    del rng
    return request.candidate - .1


def preserve_queue(request, *, rng):
    del rng
    plan = request.pool.trim_members("queue", 10)
    return ChangeResult(request.candidate - .1, edits=(plan,))


def forged_edit(request, *, rng, forbidden):
    del rng
    descriptor = request.pool.describe("elite")["descriptor"]
    return ChangeResult(request.candidate - .1,
        edits=(PoolEdit("elite", (SolutionRef(*forbidden),), expected=descriptor),))


def conflicting_edit(request, *, rng):
    del rng
    # Different parent rows deliberately disagree on an existing collection.
    selected = request.pool.main(stage="accepted").take(
        (int(request.parameters["subproblem_index"]) % 4,))
    return ChangeResult(request.candidate - .1,
        edits=(request.pool.replace_members("elite", selected.refs),))


def setup_edit_solver(kind="vns", *, batch_size=2, change=maintain_elite):
    solver, adapter = make_solver(kind, change, batch_size=batch_size)
    solver.solution_pool.create_subpool("elite")
    assert solver.step().committed  # Baseline feedback precedes any ranking.
    return solver, adapter


def assert_published_members(solver):
    pool = solver.solution_pool
    manifest = pool.snapshots.read_verified(SnapshotIdentity.from_dict(pool.publication_ref())).data
    assert manifest["retention"]["owners"]["subpool/elite"] == [
        ref.as_dict() for ref in pool.subpool_refs("elite")]
    assert manifest["subpool_metadata"]["elite"] == pool.subpool_metadata("elite")


def test_noop_edit_roundtrip_keeps_repeated_coordinates_and_revision():
    solver, _ = setup_edit_solver(change=preserve_queue)
    pool = solver.solution_pool
    first, = pool.select(stage="accepted")
    repeated = (first, first, first)
    pool.create_subpool("queue", repeated)
    before = pool.subpool_descriptor("queue")
    assert solver.step().committed
    assert pool.subpool_refs("queue") == repeated
    assert pool.subpool_descriptor("queue") == before


@pytest.mark.parametrize("kind", ["vns", "moead"])
def test_real_step_keeps_identity_and_publishes_previous_feedback_top_with_authority(kind):
    solver, _ = setup_edit_solver(kind)
    pool = solver.solution_pool
    first = pool.subpool_descriptor("elite")
    previously_accepted = pool.select(stage="accepted")
    assert solver.step().committed
    second = pool.subpool_descriptor("elite")
    assert second["view_id"] == first["view_id"] and second["revision"] == first["revision"] + 1
    # The four equal bootstrap rows in MOEA/D retain their stable input order.
    assert pool.subpool_refs("elite") == previously_accepted[:2]
    assert_published_members(solver)
    previous = pool.select(stage="accepted")
    scores, _ = pool.read_raw_feedback(previous)
    expected = tuple(previous[i] for i in sorted(range(len(previous)), key=lambda i: scores[i].sum())[:2])
    assert solver.step().committed
    assert pool.subpool_refs("elite") == expected
    assert pool.subpool_descriptor("elite")["view_id"] == first["view_id"]
    assert_published_members(solver)


@pytest.mark.parametrize("budget,accepted", [(None, (1, 3)), (3, (1,))])
def test_nonprefix_admission_and_budget_apply_one_shared_edit_only(budget, accepted):
    solver, _ = setup_edit_solver(batch_size=4)
    pool = solver.solution_pool
    before = pool.subpool_descriptor("elite")
    baseline = pool.select(stage="accepted")
    if budget is not None:
        solver.register_controller(BudgetController(max_evaluations=budget))

    class Rows:
        def select(self, candidates, feedback, context):
            return BatchDisposition(len(candidates.semantic_states), accepted)

    solver.set_evaluation_acceptance_policy(Rows())
    assert solver.step().committed
    assert pool.subpool_refs("elite") == baseline
    assert pool.subpool_descriptor("elite")["revision"] == before["revision"] + 1
    event = solver._last_evaluated_event_batch
    assert tuple(ref.candidate_token for ref in pool.subpool_refs("offspring")) == tuple(
        event.candidate_tokens[index] for index in accepted)
    assert_published_members(solver)


def test_zero_admission_keeps_old_members_identity_and_manifest():
    solver, _ = setup_edit_solver()
    before = solver.solution_pool.subpool_descriptor("elite")
    manifest = solver.solution_pool.publication_ref()

    class Reject:
        def select(self, candidates, feedback, context):
            return BatchDisposition(len(candidates.semantic_states), ())

    solver.set_evaluation_acceptance_policy(Reject())
    assert not solver.step().committed
    assert solver.solution_pool.subpool_descriptor("elite") == before
    assert solver.solution_pool.subpool_refs("elite") == ()
    assert solver.solution_pool.publication_ref() == manifest
    assert not solver.solution_pool.has_subpool("offspring")
    assert solver.evaluation_count == 3


def test_after_edit_failure_rolls_back_members_descriptor_rng_and_repeats(monkeypatch):
    solver, adapter = setup_edit_solver()
    pool = solver.solution_pool
    before = pool.subpool_descriptor("elite")
    rng = copy.deepcopy(adapter._operator_rng.bit_generator.state)
    original = solver._update_best

    def fail(*args, **kwargs):
        assert pool.subpool_refs("elite") == ()  # Staged members are not public.
        assert pool.subpool_metadata("elite")["revision"] == before["revision"] + 1
        raise RuntimeError("after edit staging")

    monkeypatch.setattr(solver, "_update_best", fail)
    with pytest.raises(RuntimeError, match="after edit staging"):
        solver.step()
    failed = np.array(solver.problem.calls[-2:], copy=True)
    assert pool.subpool_descriptor("elite") == before
    assert pool.subpool_refs("elite") == ()
    assert adapter._operator_rng.bit_generator.state == rng
    monkeypatch.setattr(solver, "_update_best", original)
    assert solver.step().committed
    np.testing.assert_array_equal(solver.problem.calls[-2:], failed)
    assert_published_members(solver)


@pytest.mark.parametrize("recreate", [False, True])
def test_post_evaluation_revision_or_name_reuse_cannot_redirect_edit(monkeypatch, recreate):
    solver, adapter = setup_edit_solver()
    pool = solver.solution_pool
    before = pool.subpool_descriptor("elite")
    members = pool.select(stage="accepted")
    update = adapter.update

    def drift(*args, **kwargs):
        update(*args, **kwargs)
        if recreate:
            pool.drop_subpool("elite")
            pool.create_subpool("elite")
        else:
            pool.add_to_subpool("elite", members)

    monkeypatch.setattr(adapter, "update", drift)
    with pytest.raises(ValueError, match="identity|revision|committed"):
        solver.step()
    assert pool.subpool_descriptor("elite") == before
    assert pool.subpool_refs("elite") == ()
    assert solver.evaluation_count == 3


@pytest.mark.parametrize("kind", ["vns", "moead"])
def test_formal_checkpoint_restores_members_and_does_not_replay_ancestor_edit(kind, tmp_path, monkeypatch):
    monkeypatch.setenv("NSGABLACK_CHECKPOINT_HMAC_KEY", "pool-edit-test-key")
    source, _ = setup_edit_solver(kind)
    assert source.step().committed
    expected_members = source.solution_pool.subpool_refs("elite")
    expected_descriptor = source.solution_pool.subpool_descriptor("elite")
    config = CheckpointResumeConfig(checkpoint_dir=str(tmp_path), save_on_finish=False)
    writer = CheckpointResumePlugin(config=config)
    source.add_plugin(writer)
    path = writer.save_checkpoint(reason="pool-edit")
    restored, adapter = make_solver(kind, maintain_elite)
    reader = CheckpointResumePlugin(config=config)
    restored.add_plugin(reader)
    assert reader.resume(str(path))
    restored.run(max_steps=0)
    assert restored.problem.calls == []
    assert restored.solution_pool.subpool_refs("elite") == expected_members
    assert restored.solution_pool.subpool_descriptor("elite") == expected_descriptor
    adapter.set_change(bare_change)
    assert restored.step().committed
    # Provenance inherits ancestor evidence, but only the current token commands.
    assert restored.solution_pool.subpool_refs("elite") == expected_members
    assert restored.solution_pool.subpool_descriptor("elite") == expected_descriptor
    assert_published_members(restored)


def test_forged_declaration_cannot_import_undeclared_member_versions():
    solver, adapter = setup_edit_solver()
    external = add_source(solver, "private", [0.])
    ref, = external
    adapter.set_change(partial(forged_edit,
        forbidden=(ref.pool_id, ref.record_id, ref.row, ref.candidate_token)))
    current = adapter.get_pool_refinement_results(solver)
    with scoped_change_access(current, subpools=("elite",), allow_main=False):
        with pytest.raises(ValueError, match="outside this change task"):
            solver.step()
    assert solver.evaluation_count == 1
    assert solver.solution_pool.subpool_refs("elite") == ()


def test_same_step_competing_replacements_are_rejected_and_all_members_roll_back():
    solver, _ = setup_edit_solver("moead", batch_size=4, change=conflicting_edit)
    before = solver.solution_pool.subpool_descriptor("elite")
    with pytest.raises(ValueError, match="conflicting replacements"):
        solver.step()
    assert solver.solution_pool.subpool_descriptor("elite") == before
    assert solver.solution_pool.subpool_refs("elite") == ()
    assert solver.evaluation_count == 8
