"""One Router archive owner joins final child members in the step transaction."""
import copy

import numpy as np
import pytest
from blackbase.contracts import BatchDisposition

from nsgablack.adapters import NSGA2Adapter, Pool, RoleSpec, StrategyRouterAdapter, MultiStrategyConfig
from nsgablack.core import ComposableSolver
from nsgablack.core.control_plane import BudgetController
from nsgablack.plugins import CheckpointResumePlugin, CheckpointResumeConfig
from nsgablack.representation import RepresentationPipeline, UniformInitializer
from nsgablack.units import UnitBinding
from benchmarks.modification_tasks import AgeBuilder
from tests.test_pool_parent_selection import Sphere


def change_left(request, *, rng):
    return request.candidate - .1


def change_right(request, *, rng):
    return request.candidate - 1.


def archive_score(pool):
    f, v = pool.raw_feedback()
    return np.column_stack((v > 0, np.maximum(v, 0), f[:, 0]))


def maintain_shared_archive(request, *, rng):
    assert request.members_by_owner is not None
    # Combined references do not pretend to share child Bias or member age.
    with pytest.raises(ValueError, match="selection feedback"):
        request.members.selection_feedback()
    for members in request.members_by_owner.values():
        assert len(members.member_field("age")) == len(members)
    old = (request.pool.subpool("shared_archive") if "shared_archive" in request.pool.describe()["subpools"]
           else request.members.take(()))
    elite = old.merge(request.members).top(3, key=archive_score)
    Pool(parent=request.pool, name="shared_archive").inject(elite, replace=True)


def conflicting_leaf_archive(request, *, rng):
    Pool(parent=request.members, name="shared_archive").inject(request.members, replace=True)


def make_solver(*, nested=False):
    left = NSGA2Adapter(name="left", population_size=4, offspring_size=4,
        change=change_left, unit_binding=UnitBinding(AgeBuilder()))
    right = NSGA2Adapter(name="right", population_size=4, offspring_size=4,
        change=change_right, unit_binding=UnitBinding(AgeBuilder()))
    router = StrategyRouterAdapter(roles=[RoleSpec("left", left), RoleSpec("right", right)],
        config=MultiStrategyConfig(total_batch_size=8, adapt_weights=False),
        pool_maintenance=maintain_shared_archive)
    if nested:
        router.set_pool_maintenance(None)
        router = StrategyRouterAdapter(roles=[RoleSpec("nested", router)],
            config=MultiStrategyConfig(total_batch_size=8, adapt_weights=False),
            pool_maintenance=maintain_shared_archive)
    solver = ComposableSolver(Sphere(), adapter=router,
        representation_pipeline=RepresentationPipeline(initializer=UniformInitializer(2., 2.)))
    solver.set_random_seed(47)
    return solver


@pytest.mark.parametrize("partial", [False, True])
def test_archive_joins_all_final_members_once_after_child_updates(partial, monkeypatch):
    solver = make_solver()
    solver.setup()
    seen = []
    operation = solver.adapter.get_bound_operator("pool_maintenance")
    original = operation.maintain
    def observe(request, *, rng):
        expected = tuple(ref for unit in solver.adapter.units
                         for ref in unit.adapter.get_population_solution_refs(solver))
        assert request.members.refs == expected
        seen.append((request, expected, len(request.accepted)))
        return original(request, rng=rng)
    monkeypatch.setattr(operation, "maintain", observe)
    try:
        assert solver.step().committed
        if partial:
            class TwoBranches:
                def select(self, candidates, feedback, context):
                    return BatchDisposition(len(candidates.semantic_states), (1, 6))
            solver.set_evaluation_acceptance_policy(TwoBranches())
        assert solver.step().committed
        assert len(seen) == 2
        assert len(seen[-1][0].members_by_owner) == 2
        assert seen[-1][2] == (2 if partial else 8)
        assert solver.evaluation_count == 16
        refs = solver.solution_pool.subpool_refs("shared_archive")
        assert len(refs) == 3
        values = solver.read_solutions(refs).numeric_matrix[:, 0]
        assert values[0] == 1.
        assert solver.adapter.population_state_mode == "partitioned"
        with pytest.raises(RuntimeError, match="ended"):
            seen[-1][0].members.all()
    finally:
        solver.teardown()


@pytest.mark.parametrize("failure", ["child", "archive", "conflict"])
def test_child_archive_or_conflicting_writer_failure_restores_all_state(failure, monkeypatch):
    solver = make_solver()
    solver.setup()
    try:
        assert solver.step().committed
        before = copy.deepcopy(solver.adapter.get_state())
        archive = solver.solution_pool.subpool_refs("shared_archive")
        manifest = solver.solution_pool.publication_ref()
        def fail(*args, **kwargs):
            raise RuntimeError("composite maintenance failure")
        if failure == "child":
            monkeypatch.setattr(solver.adapter.units[1].adapter, "update", fail)
        elif failure == "archive":
            operation = solver.adapter.get_bound_operator("pool_maintenance")
            original = operation.maintain
            def fail_after_plan(request, *, rng):
                original(request, rng=rng)
                fail()
            monkeypatch.setattr(operation, "maintain", fail_after_plan)
        else:
            solver.adapter.units[0].adapter.set_pool_maintenance(conflicting_leaf_archive)
            before = copy.deepcopy(solver.adapter.get_state())
        with pytest.raises((RuntimeError, ValueError), match="failure|conflict"):
            solver.step()
        assert solver.adapter.get_state() == before
        assert solver.solution_pool.subpool_refs("shared_archive") == archive
        assert solver.solution_pool.publication_ref() == manifest
        assert solver.evaluation_count == 16
    finally:
        solver.teardown()


def test_zero_admission_and_budget_clipping_do_not_create_unearned_maintenance(monkeypatch):
    solver = make_solver()
    solver.setup()
    try:
        assert solver.step().committed
        archived = solver.solution_pool.subpool_refs("shared_archive")
        operation = solver.adapter.get_bound_operator("pool_maintenance")
        calls = []
        original = operation.maintain
        def observe(request, *, rng):
            calls.append(len(request.accepted))
            return original(request, rng=rng)
        monkeypatch.setattr(operation, "maintain", observe)
        class Reject:
            def select(self, candidates, feedback, context):
                return BatchDisposition(len(candidates.semantic_states), ())
        solver.set_evaluation_acceptance_policy(Reject())
        assert not solver.step().committed
        assert not calls
        assert solver.solution_pool.subpool_refs("shared_archive") == archived
        solver.set_evaluation_acceptance_policy(None)
        solver.register_controller(BudgetController(max_evaluations=solver.evaluation_count+1))
        assert solver.step().committed
        assert calls == [1]
        assert solver.evaluation_budget_reserved == 0
    finally:
        solver.teardown()


def test_composite_archive_file_checkpoint_restores_binding_and_continues(tmp_path, monkeypatch):
    monkeypatch.setenv("NSGABLACK_CHECKPOINT_HMAC_KEY", "composite-archive-test")
    source, target = make_solver(), make_solver()
    config = CheckpointResumeConfig(checkpoint_dir=str(tmp_path), save_on_finish=False, strict=True)
    writer, reader = CheckpointResumePlugin(config=config), CheckpointResumePlugin(config=config)
    source.add_plugin(writer)
    target.add_plugin(reader)
    source.setup()
    try:
        assert source.step().committed and source.step().committed
        path = writer.save_checkpoint(reason="composite-archive")
        assert reader.resume(str(path))
        target.run(max_steps=0)
        assert target.problem.seen == []
        assert source.adapter.get_state() == target.adapter.get_state()
        assert source.step().committed and target.step().committed
        # Source used explicit step(), target entered a run session during
        # restore. Future proposal tokens may differ; restored existing refs
        # were compared above, and continuation must preserve search meaning.
        for a, b in zip(source.adapter.units, target.adapter.units, strict=True):
            np.testing.assert_array_equal(a.adapter.population, b.adapter.population)
            np.testing.assert_array_equal(a.adapter.algorithm_unit.age, b.adapter.algorithm_unit.age)
        np.testing.assert_array_equal(
            source.read_solutions(source.solution_pool.subpool_refs("shared_archive")).numeric_matrix,
            target.read_solutions(target.solution_pool.subpool_refs("shared_archive")).numeric_matrix)
    finally:
        source.teardown()
        target.teardown()


def test_cancelled_branch_prevents_shared_archive_update(monkeypatch):
    from nsgablack.core.state import StepOutcome
    solver = make_solver()
    solver.setup()
    try:
        assert solver.step().committed
        archive = solver.solution_pool.subpool_refs("shared_archive")
        count = solver.evaluation_count
        second = solver.adapter.units[1].adapter
        monkeypatch.setattr(second, "propose", lambda *args, **kwargs: ())
        monkeypatch.setattr(second, "get_empty_proposal_outcome", lambda *args, **kwargs:
                            StepOutcome(status="cancelled", reason="cancel archive test"))
        operation = solver.adapter.get_bound_operator("pool_maintenance")
        def forbidden(*args, **kwargs):
            raise AssertionError("cancelled proposals must not maintain an archive")
        monkeypatch.setattr(operation, "maintain", forbidden)
        outcome = solver.step()
        assert outcome.status == "cancelled"
        assert solver.evaluation_count == count
        assert solver.solution_pool.subpool_refs("shared_archive") == archive
    finally:
        solver.teardown()


def test_changed_composite_maintenance_binding_rejected_before_child_restore():
    source, target = make_solver(), make_solver()
    source.setup()
    target.setup()
    try:
        assert source.step().committed
        target.adapter.set_pool_maintenance(conflicting_leaf_archive)
        before = target.adapter.get_state()
        with pytest.raises(ValueError):
            target.adapter.set_state(source.adapter.get_state())
        assert target.adapter.get_state() == before
    finally:
        source.teardown()
        target.teardown()


def test_nested_router_uses_stable_leaf_owner_paths(monkeypatch):
    solver = make_solver(nested=True)
    solver.setup()
    seen = []
    operation = solver.adapter.get_bound_operator("pool_maintenance")
    original = operation.maintain
    def observe(request, *, rng):
        seen.append(tuple(request.members_by_owner))
        return original(request, rng=rng)
    monkeypatch.setattr(operation, "maintain", observe)
    try:
        assert solver.step().committed and solver.step().committed
        assert len(seen) == 2 and len(seen[0]) == 2
        assert seen[0] == seen[1]
        assert len(solver.solution_pool.subpool_refs("shared_archive")) == 3
    finally:
        solver.teardown()


def test_composite_members_do_not_expand_named_pool_permissions(monkeypatch):
    from nsgablack.adapters.change_access import scoped_change_access
    solver = make_solver()
    solver.setup()
    try:
        assert solver.step().committed
        solver.solution_pool.create_subpool("secret", solver.solution_pool.subpool_refs("shared_archive")[:1])
        operation = solver.adapter.get_bound_operator("pool_maintenance")
        original = operation.maintain
        def observe(request, *, rng):
            with pytest.raises(ValueError, match="declared"):
                request.pool.subpool("secret")
            assert len(request.members) == 8
            return original(request, rng=rng)
        monkeypatch.setattr(operation, "maintain", observe)
        with scoped_change_access((), subpools=("shared_archive",), allow_main=False):
            assert solver.step().committed
    finally:
        solver.teardown()
