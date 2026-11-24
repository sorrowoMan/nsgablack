"""One choose result updates Unit members and named collections atomically."""
from __future__ import annotations

import copy

import numpy as np
import pytest
from blackbase.context import SnapshotIdentity
from blackbase.contracts import BatchDisposition

from nsgablack.adapters import ChangeBatchResult, ChangeResult, NSGA2Adapter, PoolOutput
from nsgablack.core import BlackBoxProblem, ComposableSolver
from nsgablack.core.control_plane import BudgetController
from nsgablack.plugins import CheckpointResumeConfig, CheckpointResumePlugin
from nsgablack.project.scaffold.case_template_solver.pipeline.population_example import AgePopulationBuilder
from nsgablack.representation import ClipRepair, RepresentationPipeline, UniformInitializer
from nsgablack.units import UnitBinding


class RepairedSphere(BlackBoxProblem):
    def __init__(self):
        super().__init__(dimension=1, objectives=["minimize"], bounds=[(0., 1.)])
        self.calls = []

    def evaluate(self, candidate):
        values = np.array(candidate, dtype=float, copy=True)
        self.calls.append(values)
        return [float(np.dot(values, values))]


def repaired_pair(request, *, rng):
    del rng
    children = (
        ChangeResult(np.array([-4.]), source_refs=request.source_refs[:1],
                     outputs=(PoolOutput("trials", create=True),)),
        ChangeResult(np.array([4.]), source_refs=request.source_refs[1:],
                     outputs=(PoolOutput("trials", create=True),)),
    )
    return ChangeBatchResult(children[:min(2, request.max_outputs)])


def append_elite_pair(request, *, rng):
    del rng
    children = (
        ChangeResult(np.array([-4.]), outputs=(PoolOutput("elite"),)),
        ChangeResult(np.array([4.]), outputs=(PoolOutput("elite"),)),
    )
    return ChangeBatchResult(children[:min(2, request.max_outputs)])


def members_and_elite(pool):
    # Bootstrap and subsequent updates share one exact positional rule. The
    # final incoming row is retained first, then three existing positions.
    members = pool.take((len(pool) - 1, 0, 1, 2))
    return members, {"elite": members.take((2, 0))}


def members_and_late_target(pool):
    members = pool.take((len(pool) - 1, 0, 1, 2))
    return members, {"late": members.take((0,))}


def conflicting_maintenance(request, *, rng):
    del rng
    return (request.pool.replace_members("elite", request.accepted.take((0,)).refs),)


def make_solver(*, setup=True):
    adapter = NSGA2Adapter(population_size=4, offspring_size=4, change=repaired_pair,
        selector=members_and_elite, unit_binding=UnitBinding(AgePopulationBuilder()))
    solver = ComposableSolver(RepairedSphere(), adapter=adapter,
        representation_pipeline=RepresentationPipeline(initializer=UniformInitializer(.2, .8),
                                                       repair=ClipRepair(0., 1.)))
    solver.set_random_seed(413)
    if setup:
        solver.setup()
    return solver


def assert_same_manifest(solver):
    pool = solver.solution_pool
    ref = pool.publication_ref()
    manifest = pool.snapshots.read_verified(SnapshotIdentity.from_dict(ref)).data
    assert manifest["retention"]["owners"]["subpool/elite"] == [
        item.as_dict() for item in pool.subpool_refs("elite")]
    assert manifest["subpool_metadata"]["elite"] == pool.subpool_metadata("elite")
    authority = solver.snapshot_store.read_verified(solver.get_population_authority_identity().snapshot).data
    assert authority["solution_pool_ref"] == ref


@pytest.mark.parametrize("budget,accepted_indices", [(None, None), (3, (1, 2))])
def test_one_choose_preserves_repaired_versions_partial_admission_and_extended_member_fields(
    budget, accepted_indices,
):
    solver = make_solver()
    pool, adapter = solver.solution_pool, solver.adapter
    assert not pool.has_subpool("elite")
    assert solver.step().committed
    previous = adapter.get_population_solution_refs(solver)
    assert pool.subpool_refs("elite") == (previous[2], previous[0])
    descriptor = pool.subpool_descriptor("elite")
    adapter.algorithm_unit.age = np.array([10, 20, 30, 40])
    initial_accepted_count = len(pool.select(stage="accepted"))
    if budget is not None:
        solver.register_controller(BudgetController(max_evaluations=solver.evaluation_count + budget))

        class AcceptedRows:
            def select(self, candidates, feedback, context):
                return BatchDisposition(len(candidates.semantic_states), accepted_indices)

        solver.set_evaluation_acceptance_policy(AcceptedRows())
    assert solver.step().committed
    incoming = pool.select(stage="accepted")[initial_accepted_count:]
    expected_members = (incoming[-1], *previous[:3])
    assert adapter.get_population_solution_refs(solver) == expected_members
    np.testing.assert_array_equal(adapter.algorithm_unit.age, [0, 11, 21, 31])
    assert pool.subpool_refs("elite") == (expected_members[2], expected_members[0])
    current = pool.subpool_descriptor("elite")
    assert current["view_id"] == descriptor["view_id"]
    assert current["revision"] == descriptor["revision"] + 1
    assert pool.subpool_refs("trials") == incoming
    assert len(incoming) == (4 if accepted_indices is None else len(accepted_indices))
    event = solver._last_evaluated_event_batch
    accepted_rows = tuple(range(4)) if accepted_indices is None else accepted_indices
    assert tuple(ref.candidate_token for ref in incoming) == tuple(event.candidate_tokens[i] for i in accepted_rows)
    # The proposal values were -4/+4, while only repaired 0/1 versions were
    # evaluated, installed in the Unit, archived and published as trial refs.
    actual_values = solver.read_solutions(incoming).numeric_matrix
    assert np.all((actual_values == 0.) | (actual_values == 1.))
    np.testing.assert_array_equal(pool.read_raw_feedback(incoming)[0], actual_values ** 2)
    np.testing.assert_array_equal(adapter.population, solver.read_solutions(expected_members).numeric_matrix)
    assert solver.evaluation_count == 4 + (4 if budget is None else budget)
    assert_same_manifest(solver)


@pytest.mark.parametrize("conflict", ["maintenance", "append", "recreate", "absent-create"])
def test_named_side_output_conflicts_rollback_members_extension_rng_and_publication(conflict, monkeypatch):
    solver = make_solver()
    pool, adapter = solver.solution_pool, solver.adapter
    assert solver.step().committed
    adapter.algorithm_unit.age = np.array([10, 20, 30, 40])
    if conflict == "maintenance":
        adapter.set_pool_maintenance(conflicting_maintenance)
    elif conflict == "append":
        adapter.set_change(append_elite_pair)
    elif conflict == "recreate":
        ordinary_update = adapter.update

        def replace_after_selection(*args, **kwargs):
            ordinary_update(*args, **kwargs)
            pool.drop_subpool("elite")
            pool.create_subpool("elite")

        monkeypatch.setattr(adapter, "update", replace_after_selection)
    else:
        adapter.set_selector(members_and_late_target)
        ordinary_update = adapter.update

        def create_after_selection(*args, **kwargs):
            ordinary_update(*args, **kwargs)
            pool.create_subpool("late")

        monkeypatch.setattr(adapter, "update", create_after_selection)
    before = copy.deepcopy(adapter.get_state())
    descriptor, members = pool.subpool_descriptor("elite"), pool.subpool_refs("elite")
    manifest, authority = pool.publication_ref(), solver.get_population_authority_identity()
    with pytest.raises(ValueError, match="conflict|append|identity|revision|committed"):
        solver.step()
    assert adapter.get_state() == before
    np.testing.assert_array_equal(adapter.algorithm_unit.age, [10, 20, 30, 40])
    assert pool.subpool_descriptor("elite") == descriptor
    assert pool.subpool_refs("elite") == members
    assert pool.publication_ref() == manifest
    assert solver.get_population_authority_identity() == authority
    assert not pool.has_subpool("trials")
    assert not pool.has_subpool("late")
    assert solver.evaluation_count == len(solver.problem.calls) == 8


def test_zero_admission_never_executes_choose_or_creates_its_named_target(monkeypatch):
    solver = make_solver()

    class Reject:
        def select(self, candidates, feedback, context):
            return BatchDisposition(len(candidates.semantic_states), ())

    def forbidden(*args, **kwargs):
        raise AssertionError("zero admission must not select members or create archives")

    monkeypatch.setattr(solver.adapter.get_bound_selector(), "select", forbidden)
    solver.set_evaluation_acceptance_policy(Reject())
    outcome = solver.step()
    assert outcome.status == "rejected" and not outcome.committed
    assert not solver.solution_pool.has_subpool("elite")
    assert solver.solution_pool.publication_ref() is None
    assert solver.adapter.population is None
    if solver.adapter.algorithm_unit is not None:
        assert solver.adapter.algorithm_unit.age.size == 0
    assert solver.evaluation_count == 4


def test_formal_restore_keeps_new_named_target_ordered_refs_and_does_not_reselect(tmp_path, monkeypatch):
    monkeypatch.setenv("NSGABLACK_CHECKPOINT_HMAC_KEY", "selection-side-output-resume-test")
    source = make_solver()
    assert source.step().committed
    assert source.step().committed
    saved_refs = source.solution_pool.select(stage=None)
    elite = source.solution_pool.subpool_refs("elite")
    descriptor = source.solution_pool.subpool_descriptor("elite")
    adapter_state = copy.deepcopy(source.adapter.get_state())
    config = CheckpointResumeConfig(checkpoint_dir=str(tmp_path), save_on_finish=False, strict=True)
    writer = CheckpointResumePlugin(config=config)
    source.add_plugin(writer)
    checkpoint = writer.save_checkpoint(reason="selection-side-output")
    assert checkpoint is not None

    restored = make_solver(setup=False)
    reader = CheckpointResumePlugin(config=config)
    restored.add_plugin(reader)

    def forbidden(*args, **kwargs):
        raise AssertionError("restore must not regenerate candidates or reselect archived members")

    with monkeypatch.context() as restore_only:
        restore_only.setattr(restored.representation_pipeline.initializer, "initialize", forbidden)
        restore_only.setattr(restored.adapter.get_bound_selector(), "select", forbidden)
        assert reader.resume(str(checkpoint))
        restored.run(max_steps=0)
    assert restored.problem.calls == []
    assert restored.solution_pool.select(stage=None) == saved_refs
    assert restored.solution_pool.subpool_refs("elite") == elite
    assert restored.solution_pool.subpool_descriptor("elite") == descriptor
    assert restored.adapter.get_state() == adapter_state
    np.testing.assert_array_equal(restored.read_solutions(elite).numeric_matrix,
                                  source.read_solutions(elite).numeric_matrix)
    assert_same_manifest(restored)

    before_evaluations = len(source.problem.calls)
    assert source.step().committed
    assert restored.step().committed
    np.testing.assert_array_equal(restored.problem.calls, source.problem.calls[before_evaluations:])
    np.testing.assert_array_equal(restored.adapter.population, source.adapter.population)
    np.testing.assert_array_equal(restored.adapter.algorithm_unit.age, source.adapter.algorithm_unit.age)
    assert restored.adapter._rng.bit_generator.state == source.adapter._rng.bit_generator.state
    assert restored.solution_pool.subpool_descriptor("elite") == source.solution_pool.subpool_descriptor("elite")
    actual = restored.solution_pool.subpool_refs("elite")
    expected = source.solution_pool.subpool_refs("elite")
    np.testing.assert_array_equal(restored.read_solutions(actual).numeric_matrix,
                                  source.read_solutions(expected).numeric_matrix)
    assert_same_manifest(restored)
