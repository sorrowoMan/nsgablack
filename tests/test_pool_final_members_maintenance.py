"""Maintenance observes the leaf's final ordered members, not all admissions."""
from __future__ import annotations

import copy

import numpy as np
import pytest
from blackbase.contracts import BatchDisposition
from blackbase.types import CandidateBatch, Feedback

from nsgablack.adapters import ChangeBatchResult, ChangeResult, MOEADAdapter, NSGA2Adapter, VNSAdapter
from nsgablack.core import BlackBoxProblem, ComposableSolver
from nsgablack.core.control_plane import BudgetController
from nsgablack.core.evaluation_feedback import OptimizationFeedbackBatch
from nsgablack.plugins import CheckpointResumeConfig, CheckpointResumePlugin
from nsgablack.representation import ClipRepair, RepresentationPipeline, UniformInitializer


class MaintenanceSphere(BlackBoxProblem):
    def __init__(self, objectives=1):
        super().__init__(dimension=1, objectives=["minimize"] * objectives, bounds=[(0., 1.)])
        self.calls = []

    def evaluate(self, candidate):
        row = np.array(candidate, dtype=float, copy=True)
        self.calls.append(row)
        return [float(row @ row)] * self.get_num_objectives()


def repaired_pair(request, *, rng):
    del rng
    return ChangeBatchResult(tuple(ChangeResult(np.array([value]))
        for value in (-4., 4.)[:min(2, request.max_outputs)]))


def keep_old_three_and_worst_incoming(pool):
    if len(pool) == 4:
        return pool.sort(lambda rows: rows.objectives[:, 0]).take(range(4))
    # A legal custom algorithm decision deliberately drops the better trial.
    incoming = 4 + int(np.argmax(pool.objectives[4:, 0]))
    return pool.take((incoming, 1, 2, 3))


def raw_score(pool):
    return pool.raw_feedback()[0][:, 0]


def archive_final_members(request, *, rng):
    del rng
    members = request.members
    assert members is not None
    names = request.pool.describe()["subpools"]
    previous = request.pool.subpool("archive") if "archive" in names else members.take(())
    elite = previous.merge(members).top(2, key=raw_score)
    # Empty collections are intentional, and creation itself remains staged.
    return (request.pool.replace_members("archive", elite.refs, create=True),
            request.pool.replace_members("empty", (), create=True))


def archive_late_members(request, *, rng):
    return (*archive_final_members(request, rng=rng),
            request.pool.replace_members("late", request.members.take((0,)).refs, create=True))


def copy_slot_members(request, *, rng):
    del rng
    assert request.members is not None
    return (request.pool.replace_members("slots", request.members.refs, create=True),)


def no_population_maintenance(request, *, rng):
    del rng
    assert request.members is None
    assert len(request.accepted) > 0
    np.testing.assert_array_equal(request.accepted.objectives, request.objectives)
    return (request.pool.replace_members("trajectory_trials", request.accepted.refs, create=True),)


def dominating_change(request, *, rng):
    del request, rng
    return ChangeResult(np.array([0.]))


def make_solver(*, setup=True):
    adapter = NSGA2Adapter(population_size=4, offspring_size=4, change=repaired_pair,
        selector=keep_old_three_and_worst_incoming, pool_maintenance=archive_final_members)
    solver = ComposableSolver(MaintenanceSphere(), adapter=adapter,
        representation_pipeline=RepresentationPipeline(initializer=UniformInitializer(.2, .8),
                                                       repair=ClipRepair(0., 1.)))
    solver.set_random_seed(783)
    if setup:
        solver.setup()
    return solver


def observe_maintenance(monkeypatch, solver):
    operation = solver.adapter.get_bound_operator("pool_maintenance")
    ordinary = operation.maintain
    seen = []

    def observe(request, *, rng):
        members = request.members
        seen.append(dict(request=request, accepted=request.accepted.refs,
            accepted_f=np.array(request.accepted.objectives, copy=True),
            members=None if members is None else members.refs,
            member_f=None if members is None else np.array(members.objectives, copy=True)))
        if members is not None:
            np.testing.assert_array_equal(members.values, solver.adapter.get_population_snapshot()[0])
            np.testing.assert_array_equal(members.objectives, solver.adapter.get_population_snapshot()[1])
            np.testing.assert_array_equal(members.violations, solver.adapter.get_population_snapshot()[2])
            with pytest.raises(ValueError):
                members.objectives.setflags(write=True)
        return ordinary(request, rng=rng)

    monkeypatch.setattr(operation, "maintain", observe)
    return seen


@pytest.mark.parametrize("partial", [False, True])
def test_history_plus_final_members_excludes_better_rejected_trials_and_creates_empty_target(partial, monkeypatch):
    solver = make_solver()
    seen = observe_maintenance(monkeypatch, solver)
    assert not solver.solution_pool.has_subpool("archive")
    assert solver.step().committed
    pool, adapter = solver.solution_pool, solver.adapter
    initial = adapter.get_population_solution_refs(solver)
    historic_best = pool.subpool_refs("archive")[0]
    descriptor = pool.subpool_descriptor("archive")
    assert historic_best == initial[0]
    assert pool.subpool_refs("empty") == ()
    if partial:
        solver.register_controller(BudgetController(max_evaluations=solver.evaluation_count + 3))

        class NonprefixAcceptance:
            def select(self, candidates, feedback, context):
                return BatchDisposition(len(candidates.semantic_states), (1, 2))

        solver.set_evaluation_acceptance_policy(NonprefixAcceptance())
    assert solver.step().committed
    observation = seen[-1]
    members, accepted = observation["members"], observation["accepted"]
    assert members == adapter.get_population_solution_refs(solver)
    assert members[1:] == initial[1:]
    excluded = tuple(ref for ref in accepted if ref not in members)
    assert excluded and np.min(pool.read_raw_feedback(excluded)[0]) == 0.
    assert np.min(pool.read_raw_feedback(pool.subpool_refs("archive"))[0]) > 0.
    assert not set(excluded).intersection(pool.subpool_refs("archive"))
    assert historic_best not in members and historic_best in pool.subpool_refs("archive")
    assert len(accepted) == (2 if partial else 4)
    assert solver.evaluation_count == len(solver.problem.calls) == (7 if partial else 8)
    assert pool.subpool_descriptor("archive")["view_id"] == descriptor["view_id"]
    # Replacing exactly the same ordered members is idempotent.
    assert pool.subpool_descriptor("archive") == descriptor
    event = solver._last_evaluated_event_batch
    rows = (1, 2) if partial else range(4)
    assert tuple(ref.candidate_token for ref in accepted) == tuple(event.candidate_tokens[i] for i in rows)
    assert np.all((solver.read_solutions(accepted).numeric_matrix == 0.) |
                  (solver.read_solutions(accepted).numeric_matrix == 1.))
    with pytest.raises(RuntimeError, match="ended"):
        observation["request"].members.all()
    # An old archive member is not among the next selection's offered rows.
    if not partial:
        offered = (*members,)
        assert historic_best not in offered
        assert solver.step().committed
        assert historic_best not in seen[-1]["accepted"]
        assert historic_best in pool.subpool_refs("archive")


@pytest.mark.parametrize("drift", ["revision", "recreate", "absent-create"])
def test_maintenance_target_drift_rolls_back_unit_rng_and_pool_but_keeps_evaluations(drift, monkeypatch):
    solver = make_solver()
    assert solver.step().committed
    pool, adapter = solver.solution_pool, solver.adapter
    if drift == "absent-create":
        adapter.set_pool_maintenance(archive_late_members)
    old_update = adapter.update

    def drift_after_maintenance(*args, **kwargs):
        old_update(*args, **kwargs)
        if drift == "revision":
            pool.replace_subpool_members("archive", tuple(reversed(pool.subpool_refs("archive"))))
        elif drift == "recreate":
            pool.drop_subpool("archive")
            pool.create_subpool("archive")
        else:
            pool.create_subpool("late")

    monkeypatch.setattr(adapter, "update", drift_after_maintenance)
    before = copy.deepcopy(adapter.get_state())
    refs, descriptor = pool.subpool_refs("archive"), pool.subpool_descriptor("archive")
    manifest, authority = pool.publication_ref(), solver.get_population_authority_identity()
    with pytest.raises(ValueError, match="identity|revision|committed"):
        solver.step()
    assert adapter.get_state() == before
    assert pool.subpool_refs("archive") == refs
    assert pool.subpool_descriptor("archive") == descriptor
    assert pool.publication_ref() == manifest
    assert solver.get_population_authority_identity() == authority
    assert not pool.has_subpool("late")
    assert solver.evaluation_count == len(solver.problem.calls) == 8


def test_final_member_archives_restore_without_initialization_evaluation_or_maintenance_replay(tmp_path, monkeypatch):
    monkeypatch.setenv("NSGABLACK_CHECKPOINT_HMAC_KEY", "final-member-maintenance-test")
    source = make_solver()
    assert source.step().committed and source.step().committed
    config = CheckpointResumeConfig(checkpoint_dir=str(tmp_path), save_on_finish=False, strict=True)
    writer = CheckpointResumePlugin(config=config)
    source.add_plugin(writer)
    checkpoint = writer.save_checkpoint(reason="final-members")
    assert checkpoint is not None
    saved = copy.deepcopy(source.adapter.get_state())
    refs = source.solution_pool.select(stage=None)
    archives = {name: (source.solution_pool.subpool_descriptor(name), source.solution_pool.subpool_refs(name))
                for name in ("archive", "empty")}
    restored = make_solver(setup=False)
    reader = CheckpointResumePlugin(config=config)
    restored.add_plugin(reader)

    def forbidden(*args, **kwargs):
        raise AssertionError("restoring final-member output must not replay work")

    with monkeypatch.context() as restore_only:
        restore_only.setattr(restored.representation_pipeline.initializer, "initialize", forbidden)
        restore_only.setattr(restored.adapter.get_bound_selector(), "select", forbidden)
        restore_only.setattr(restored.adapter.get_bound_operator("pool_maintenance"), "maintain", forbidden)
        assert reader.resume(str(checkpoint))
        restored.run(max_steps=0)
    assert restored.problem.calls == []
    assert restored.adapter.get_state() == saved
    assert restored.solution_pool.select(stage=None) == refs
    for name, (descriptor, members) in archives.items():
        assert restored.solution_pool.subpool_descriptor(name) == descriptor
        assert restored.solution_pool.subpool_refs(name) == members
    evaluated = len(source.problem.calls)
    assert source.step().committed and restored.step().committed
    np.testing.assert_array_equal(restored.problem.calls, source.problem.calls[evaluated:])
    np.testing.assert_array_equal(restored.adapter.population, source.adapter.population)
    assert restored.adapter._rng.bit_generator.state == source.adapter._rng.bit_generator.state
    assert restored.solution_pool.subpool_descriptor("archive") == source.solution_pool.subpool_descriptor("archive")
    np.testing.assert_array_equal(restored.read_solutions(restored.solution_pool.subpool_refs("archive")).numeric_matrix,
                                  source.read_solutions(source.solution_pool.subpool_refs("archive")).numeric_matrix)


def test_vns_does_not_pretend_trajectory_results_are_a_population():
    adapter = VNSAdapter(batch_size=2, change=dominating_change, pool_maintenance=no_population_maintenance)
    solver = ComposableSolver(MaintenanceSphere(), adapter=adapter,
        representation_pipeline=RepresentationPipeline(initializer=UniformInitializer(.2, .8), repair=ClipRepair(0., 1.)))
    solver.set_random_seed(43)
    solver.setup()
    assert solver.step().committed
    assert solver.solution_pool.subpool_refs("trajectory_trials")


@pytest.mark.filterwarnings("ignore:MOEADAdapter did not detect an archive plugin:RuntimeWarning")
def test_moead_final_members_keep_repeated_slots_and_original_vector_feedback(monkeypatch):
    adapter = MOEADAdapter(population_size=4, neighborhood_size=4, batch_size=1, nr=4,
        change=dominating_change, pool_maintenance=copy_slot_members)
    solver = ComposableSolver(MaintenanceSphere(objectives=2), adapter=adapter,
        representation_pipeline=RepresentationPipeline(initializer=UniformInitializer(.2, .8), repair=ClipRepair(0., 1.)))
    solver.set_random_seed(62)
    solver.setup()
    seen = observe_maintenance(monkeypatch, solver)
    assert solver.step().committed
    assert solver.step().committed
    slots = adapter.get_population_solution_refs(solver)
    assert len(slots) == 4 and len(set(slots)) == 1
    assert seen[-1]["members"] == slots
    assert solver.solution_pool.subpool_refs("slots") == slots
    assert len(seen[-1]["accepted"]) == 1
    np.testing.assert_array_equal(seen[-1]["member_f"], np.zeros((4, 2)))
    np.testing.assert_array_equal(solver.solution_pool.read_raw_feedback(slots)[0], np.zeros((4, 2)))


def test_restricted_maintenance_receives_owned_members_without_broadening_task_read_or_create_permissions(monkeypatch):
    from nsgablack.adapters.change_access import scoped_change_access

    solver = make_solver()
    assert solver.step().committed
    adapter, pool = solver.adapter, solver.solution_pool
    own = adapter.get_population_solution_refs(solver)
    pool.create_subpool("secret", own[:1])
    operation = adapter.get_bound_operator("pool_maintenance")
    ordinary = operation.maintain
    seen = []

    def constrained_maintenance(request, *, rng):
        seen.append(request.members.refs)
        # None of the old population was supplied as this task's seed.
        assert set(own[1:]).issubset(request.members.refs)
        np.testing.assert_array_equal(request.pool.read(own[1:]).values,
                                      solver.read_solutions(own[1:]).numeric_matrix)
        with pytest.raises(ValueError, match="mother pool"):
            request.pool.main()
        with pytest.raises(ValueError, match="declared inputs"):
            request.pool.subpool("secret")
        with pytest.raises(ValueError, match="declared inputs"):
            request.pool.replace_members("undeclared", request.members.refs, create=True)
        return (*ordinary(request, rng=rng),
                request.pool.replace_members("declared_new", request.members.refs, create=True))

    monkeypatch.setattr(operation, "maintain", constrained_maintenance)
    update = adapter.update

    def restricted_update(*args, **kwargs):
        with scoped_change_access((), subpools=("archive", "empty", "declared_new"), allow_main=False):
            return update(*args, **kwargs)

    monkeypatch.setattr(adapter, "update", restricted_update)
    assert solver.step().committed
    assert seen[-1] == pool.subpool_refs("declared_new")
    assert not pool.has_subpool("undeclared")
    assert pool.subpool_refs("secret") == own[:1]


@pytest.mark.parametrize("invalid", ["missing-refs", "missing-snapshot", "wrong-rows", "wrong-values", "sibling-pending"])
def test_final_member_contract_rejects_partial_or_false_delivery_and_sibling_pending(invalid, monkeypatch):
    solver = make_solver()
    assert solver.step().committed
    adapter, pool = solver.adapter, solver.solution_pool
    before = copy.deepcopy(adapter.get_state())
    descriptor = pool.subpool_descriptor("archive")
    snapshot = adapter.get_population_snapshot
    refs = adapter.get_population_solution_refs
    update = adapter.update

    def sibling_refs(control):
        owned = refs(control)
        row = adapter.population[0]
        sibling = pool.put(CandidateBatch.from_candidates((row,), candidate_tokens=("sibling-pending",)),
            stage="accepted", feedback=OptimizationFeedbackBatch.from_feedback(
                (Feedback(objectives=[float(row @ row)]),), violations=[0.]))
        return (*sibling, *owned[1:])

    def invalid_update(*args, **kwargs):
        # Only corrupt the final delivery. Propose must still use its true
        # population refs so this checks the post-evaluation boundary.
        with monkeypatch.context() as bad:
            if invalid == "missing-refs":
                bad.setattr(adapter, "get_population_solution_refs", lambda control: None)
            elif invalid == "missing-snapshot":
                bad.setattr(adapter, "get_population_snapshot", lambda: None)
            elif invalid == "wrong-rows":
                bad.setattr(adapter, "get_population_snapshot",
                            lambda: (snapshot()[0], snapshot()[1][:-1], snapshot()[2]))
            elif invalid == "wrong-values":
                bad.setattr(adapter, "get_population_snapshot",
                            lambda: (snapshot()[0] + 3., snapshot()[1], snapshot()[2]))
            else:
                bad.setattr(adapter, "get_population_solution_refs", sibling_refs)
            return update(*args, **kwargs)

    monkeypatch.setattr(adapter, "update", invalid_update)
    with pytest.raises(ValueError, match="align|rows|differs|uncommitted"):
        solver.step()
    assert adapter.get_state() == before
    assert pool.subpool_descriptor("archive") == descriptor
    assert not any(ref.candidate_token == "sibling-pending" for ref in pool.select(stage=None))
    assert solver.evaluation_count == len(solver.problem.calls) == 8


def test_create_flag_keeps_default_missing_target_error_and_cannot_replace_algorithm_view():
    from nsgablack.adapters.change_pool import ChangePool

    solver = make_solver()
    assert solver.step().committed
    pool = solver.solution_pool
    name, = tuple(name for name in pool.published_subpool_names()
                  if pool.subpool_metadata(name)["kind"] == "candidate_view")
    scope = ChangePool(pool)
    try:
        with pytest.raises(KeyError, match="does not exist"):
            scope.replace_members("absent", ())
        plan = scope.replace_members("absent", (), create=True)
        assert plan.expected == {"pool_id": pool.pool_id, "name": "absent", "absent": True}
        assert not pool.has_subpool("absent")
        with pytest.raises(ValueError, match="ordinary candidate_collection"):
            scope.replace_members(name, (), create=True)
    finally:
        scope.close()
