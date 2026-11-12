from types import SimpleNamespace

import numpy as np
import pytest

from nsgablack.adapters.pool_partition import partition
from nsgablack.adapters.selection_pool import offered_pool
from tests.test_pool_survivor_selection import make_control, put


def test_fields_follow_occurrences_nested_choices_and_partition():
    control = make_control()
    a, b, c = put(control)
    unit = SimpleNamespace(population=np.array([[1.], [1.], [2.]]),
        member_fields=("age", "velocity", "labels"), labels=[{"group": "x"}, {"group": "y"}, {"group": "z"}], age=np.array([1, 5, 2]),
        velocity=np.array([[1., 2.], [3., 4.], [5., 6.]]))
    with offered_pool(control, (a, a, b, c), objectives=[[1.]]*4, violations=[0.]*4,
                      unit=unit, member_rows=(0, 1, 2, None)) as pool:
        unit.age[:] = 99  # The invocation captured detached fields.
        view = pool.take((3, 1, 0))
        assert view.member_field("age", default=0).tolist() == [0, 5, 1]
        assert [v["group"] for v in view.member_field("labels", default={"group": "new"})] == ["new", "y", "x"]
        with pytest.raises(TypeError):
            view.member_field("labels", default=None)[1]["group"] = "changed"
        assert view.member_field("velocity", default=[0., 0.]).tolist() == [[0., 0.], [3., 4.], [1., 2.]]
        chosen = view.chosen(lambda p: p.take(np.flatnonzero(p.member_field("age", default=0) < 2)))
        assert chosen.refs == (c, a)
        selected, rest = partition(view, by=lambda p: p.take(np.flatnonzero(p.member_field("age", default=0) > 2)))
        assert selected.member_field("age", default=0).tolist() == [5]
        assert rest.member_field("age", default=0).tolist() == [0, 1]
        assert pool.take(()).member_field("velocity", default=[0., 0.]).shape == (0, 2)
        with pytest.raises(ValueError):
            pool.member_field("age", default=0).setflags(write=True)
        with pytest.raises(KeyError):
            pool.member_field("typo", default=0)
        with pytest.raises(ValueError):
            pool.member_field("velocity", default=0)
    with pytest.raises(RuntimeError):
        view.member_field("age", default=0)


@pytest.mark.parametrize("rows", [(0,), (0, 4, None), (0, True, None)])
def test_invalid_owner_coordinates_rejected(rows):
    control = make_control()
    refs = put(control)
    unit = SimpleNamespace(population=np.zeros((2, 1)), member_fields=("age",), age=np.zeros(2))
    with pytest.raises(ValueError):
        with offered_pool(control, refs, objectives=[[1.]]*3, violations=[0.]*3,
                          unit=unit, member_rows=rows):
            pass


def archive_young_final_members(request, *, rng):
    from nsgablack.adapters import Pool
    from nsgablack.adapters.pool_partition import partition
    del rng
    young, old = partition(request.members,
        by=lambda p: p.where(lambda q: q.member_field("age", default=0) < 1))
    # Multiple operations still carry the final owner's slots.
    combined = young.concat(old).order_by(lambda p: p.member_field("age", default=0))
    elite = combined.top(2, key=lambda p: p.objectives[:, 0])
    Pool(parent=request.members, name="member_elite").inject(elite, replace=True)


def make_member_solver():
    from tests.test_pool_final_members_maintenance import make_solver
    from benchmarks.modification_tasks import AgeBuilder
    from nsgablack.units import UnitBinding
    solver = make_solver(setup=False)
    solver.adapter.set_unit_binding(UnitBinding(AgeBuilder()))
    solver.adapter.set_pool_maintenance(archive_young_final_members)
    return solver


def choose_age_count(pool, *, count):
    return pool.top(count, key=lambda p: p.member_field("age", default=0))


def test_partial_bootstrap_uses_current_count_then_fills_population_without_rebinding():
    from blackbase.contracts import BatchDisposition
    solver = make_member_solver()
    solver.adapter.set_selector(choose_age_count)
    class BootstrapAdmission:
        def select(self, candidates, feedback, context):
            n = len(candidates.semantic_states)
            return BatchDisposition(n, (0, 2) if solver.adapter.algorithm_unit.objectives is None
                                    else tuple(range(n)))
    solver.set_evaluation_acceptance_policy(BootstrapAdmission())
    solver.setup()
    try:
        assert solver.step().committed
        assert len(solver.adapter.algorithm_unit.population) == 2
        assert solver.adapter.algorithm_unit.age.tolist() == [0, 0]
        assert solver.step().committed
        assert len(solver.adapter.algorithm_unit.population) == 4
        assert solver.adapter.algorithm_unit.age.tolist() == [1, 1, 0, 0]
        assert len(solver.solution_pool.subpool_refs("member_elite")) == 2
    finally:
        solver.teardown()


def test_final_members_field_selection_publication_and_failure_rollback(monkeypatch):
    solver = make_member_solver()
    solver.setup()
    try:
        assert solver.step().committed
        assert solver.step().committed
        refs = solver.adapter.get_population_solution_refs(solver)
        unit = solver.adapter.algorithm_unit
        assert unit.age.tolist() == [0, 1, 1, 1]
        expected = tuple(refs[i] for i in np.argsort(unit.objectives[:, 0], kind="stable")[:2])
        assert solver.solution_pool.subpool_refs("member_elite") == expected
        ages = unit.age.copy()
        operation = solver.adapter.get_bound_operator("pool_maintenance")
        original = operation.maintain
        def fail_after_planning(request, *, rng):
            original(request, rng=rng)
            raise ValueError("planned archive failure")
        monkeypatch.setattr(operation, "maintain", fail_after_planning)
        evaluations = solver.evaluation_count
        with pytest.raises(ValueError, match="planned archive failure"):
            solver.step()
        np.testing.assert_array_equal(solver.adapter.algorithm_unit.age, ages)
        assert solver.adapter.get_population_solution_refs(solver) == refs
        assert solver.solution_pool.subpool_refs("member_elite") == expected
        assert solver.evaluation_count > evaluations
    finally:
        solver.teardown()


def test_final_members_field_checkpoint_continuation(tmp_path, monkeypatch):
    from nsgablack.plugins import CheckpointResumePlugin, CheckpointResumeConfig
    monkeypatch.setenv("NSGABLACK_CHECKPOINT_HMAC_KEY", "member-fields-test")
    source, target = make_member_solver(), make_member_solver()
    config = CheckpointResumeConfig(checkpoint_dir=str(tmp_path), save_on_finish=False, strict=True)
    writer, reader = CheckpointResumePlugin(config=config), CheckpointResumePlugin(config=config)
    source.add_plugin(writer)
    target.add_plugin(reader)
    source.setup()
    try:
        assert source.step().committed and source.step().committed
        path = writer.save_checkpoint(reason="member-fields")
        assert reader.resume(str(path))
        target.run(max_steps=0)
        np.testing.assert_array_equal(source.adapter.algorithm_unit.age, target.adapter.algorithm_unit.age)
        assert source.step().committed and target.step().committed
        np.testing.assert_array_equal(source.adapter.algorithm_unit.age, target.adapter.algorithm_unit.age)
        assert source.solution_pool.subpool_refs("member_elite") == target.solution_pool.subpool_refs("member_elite")
    finally:
        source.teardown()
        target.teardown()


def test_cross_root_merge_requires_explicit_scoring_and_does_not_guess_member_owner():
    control = make_control()
    refs = put(control)
    unit = SimpleNamespace(population=np.zeros((3, 1)), member_fields=("age",), age=np.array([4, 2, 1]))
    with offered_pool(control, refs, objectives=[[-1.], [-2.], [-3.]], violations=[0.]*3,
                      unit=unit, member_rows=(0, 1, 2)) as pool:
        # Re-reading exact refs from the store does not grant this Unit's slots.
        other = pool._scope.read((refs[2],))
        combined = pool.take((0,)).concat(other)
        with pytest.raises(ValueError, match="raw_feedback"):
            combined.objectives
        with pytest.raises(KeyError, match="before combining"):
            combined.member_field("age", default=0)
        ordered = combined.top(2, key=lambda p: p.raw_feedback()[0][:, 0])
        assert ordered.refs == (refs[0], refs[2])


def test_scalar_member_field_fails_with_alignment_error():
    control = make_control()
    refs = put(control)
    unit = SimpleNamespace(population=np.zeros((3, 1)), member_fields=("age",), age=np.array(1))
    with pytest.raises(ValueError, match="align"):
        with offered_pool(control, refs, objectives=[[1.]]*3, violations=[0.]*3,
                          unit=unit, member_rows=(0, 1, 2)):
            pass


def test_exact_integer_fields_survive_default_fill_sort_and_repeated_slots():
    control = make_control()
    a, b, c = put(control)
    huge = 2**64 - 1
    unit = SimpleNamespace(population=np.zeros((2, 1)), member_fields=("label_id",),
                           label_id=np.array([huge, huge-1], dtype=np.uint64))
    with offered_pool(control, (a, a, c), objectives=[[1.]]*3, violations=[0.]*3,
                      unit=unit, member_rows=(0, 1, None)) as pool:
        ids = pool.member_field("label_id", default=0)
        assert ids.dtype == np.uint64
        assert ids.tolist() == [huge, huge-1, 0]
        chosen = pool.order_by(lambda p: p.member_field("label_id", default=0))
        assert chosen.refs == (c, a, a)
        assert chosen.member_field("label_id", default=0).tolist() == [0, huge-1, huge]
        with pytest.raises(ValueError, match="exact integer"):
            pool.member_field("label_id", default=-1)
        with pytest.raises(ValueError, match="precision"):
            pool.member_field("label_id", default=.5)


def test_final_member_read_needs_no_default_but_new_proposals_do():
    control = make_control()
    refs = put(control)
    unit = SimpleNamespace(population=np.zeros((2, 1)), member_fields=("age",), age=np.array([2, 5]))
    with offered_pool(control, refs, objectives=[[1.]]*3, violations=[0.]*3,
                      unit=unit, member_rows=(1, 0, None)) as pool:
        assert pool.take((0, 1)).member_field("age").tolist() == [5, 2]
        with pytest.raises(ValueError, match="new proposals; specify default"):
            pool.member_field("age")


def test_structured_fields_reuse_unit_codec_and_detach_nested_numpy_data(monkeypatch):
    import nsgablack.units.features as features
    def no_digest(*args, **kwargs):
        raise AssertionError("call-local member reads must not compute feature digests")
    monkeypatch.setattr(features, "_snapshot", no_digest)
    control = make_control()
    refs = put(control)
    source = np.array([1., 2.])
    unit = SimpleNamespace(population=np.zeros((2, 1)), member_fields=("stats",),
        stats=[{"vector": source, "size": np.int64(2)}, {"vector": source+2}])
    with offered_pool(control, refs, objectives=[[1.]]*3, violations=[0.]*3,
                      unit=unit, member_rows=(1, 0, None)) as pool:
        source[:] = -1
        values = pool.member_field("stats", default={"vector": np.zeros(2)})
        assert values[1]["vector"].tolist() == [1., 2.]
        assert values[2]["vector"].tolist() == [0., 0.]
        with pytest.raises(ValueError):
            values[1]["vector"].setflags(write=True)
        with pytest.raises(TypeError):
            values[1]["size"] = 3


def test_text_member_sequences_remain_readable_after_unit_codec_detachment():
    control = make_control()
    refs = put(control)
    unit = SimpleNamespace(population=np.zeros((2, 1)), member_fields=("role",),
                           role=["explore", "exploit"])
    with offered_pool(control, refs, objectives=[[1.]]*3, violations=[0.]*3,
                      unit=unit, member_rows=(1, 0, None)) as pool:
        assert tuple(pool.member_field("role", default="new")) == ("exploit", "explore", "new")
