"""Real control-plane steps for pool inputs, composed changes and destinations."""
from __future__ import annotations

import copy
from functools import partial

import numpy as np
import pytest
from blackbase.contracts import BatchDisposition
from blackbase.types import CandidateBatch

from nsgablack.adapters import ChangeResult, MOEADAdapter, PoolOutput, VNSAdapter
from nsgablack.core import BlackBoxProblem, ComposableSolver
from nsgablack.core.control_plane import BudgetController
from nsgablack.core.state.pool_views import ObjectiveProjection
from nsgablack.core.state.solution_pool import SolutionRef
from nsgablack.plugins import CheckpointResumeConfig, CheckpointResumePlugin
from nsgablack.representation import ClipRepair, RepresentationPipeline, UniformInitializer


class RecordedProblem(BlackBoxProblem):
    def __init__(self, objectives=1):
        super().__init__(dimension=1, objectives=["minimize"] * objectives,
                         bounds=[(-100., 100.)])
        self.calls = []
        self.objective_count = objectives

    def evaluate(self, candidate):
        x = np.array(candidate, dtype=float, copy=True)
        self.calls.append(x)
        return ([float(x[0] ** 2)] if self.objective_count == 1
                else [float(x[0] ** 2), float((x[0] - 3.) ** 2)])


def pool_average(request, *, rng):
    anchor = request.pool.read(request.source_refs).take((0,))
    elite = request.pool.subpool("elite").random(1, rng=rng)
    parents = anchor.merge(elite)
    values = parents.values
    assert not values.flags.writeable
    with pytest.raises(ValueError):
        values.flags.writeable = True
    return ChangeResult(np.mean(values, axis=0),
                        outputs=(PoolOutput("offspring", create=True),))


def pool_random_change(request, *, rng):
    elite = request.pool.subpool("elite").random(1, rng=rng)
    values = elite.values
    child = (request.candidate + values[0]) / 2. + rng.uniform(-.1, .1, size=1)
    return ChangeResult(child, outputs=(PoolOutput("offspring", create=True),))


def source_composition(request, *, rng, mutate_first=False):
    del rng
    left = request.pool.main(stage="initial", source="left").take((0,))
    right = request.pool.main(stage="initial", source="right").take((0,))
    parents = left.merge(right).values
    # Squaring makes the difference between the two compositions observable.
    child = np.mean((parents + 1.) ** 2, axis=0) if mutate_first else (np.mean(parents, axis=0) + 1.) ** 2
    return ChangeResult(child, outputs=(PoolOutput("offspring", create=True),))


def write_target(request, *, rng, name, create=False):
    del rng
    return ChangeResult(request.candidate - .5,
                        outputs=(PoolOutput(name, create=create),))


def no_output_change(request, *, rng):
    del rng
    return request.candidate - .25


def outside_bounds_change(request, *, rng):
    del rng
    return ChangeResult(request.candidate + 200.,
                        outputs=(PoolOutput("offspring", create=True),))


def make_solver(kind="vns", change=pool_average, *, batch_size=2, setup=True):
    adapter = (VNSAdapter(change=change, batch_size=batch_size, k_max=3,
                          restart_on_stagnation=False) if kind == "vns"
               else MOEADAdapter(change=change, population_size=4,
                                  neighborhood_size=4, batch_size=batch_size,
                                  variation="de", nr=2))
    pipeline = RepresentationPipeline(initializer=UniformInitializer(low=4., high=4.),
                                      repair=ClipRepair(low=-100., high=100.))
    solver = ComposableSolver(RecordedProblem(1 if kind == "vns" else 2),
                              adapter=adapter, representation_pipeline=pipeline)
    solver.set_random_seed(91)
    if setup:
        solver.setup()
    return solver, adapter


def add_source(solver, name, values):
    refs = solver.store_solutions(CandidateBatch.from_candidates(
        [[float(value)] for value in values],
        candidate_tokens=tuple(f"{name}:{index}" for index in range(len(values)))),
        source=name)
    solver.solution_pool.create_subpool(name, refs)
    return refs


def supplied_refs(solver):
    return tuple(tuple(SolutionRef.from_dict(ref) for ref in item.metadata["change_input_refs"])
                 for item in solver._last_evaluated_event_provenance)


def output_values(solver):
    refs = solver.solution_pool.subpool_refs("offspring")
    return refs, solver.read_solutions(refs).numeric_matrix


def test_vns_uses_elite_pool_in_addition_to_current_without_rewriting_sources():
    solver, adapter = make_solver()
    elite = add_source(solver, "elite", [0.])
    assert solver.step().committed
    current, = adapter.get_pool_refinement_results(solver)
    before = np.array(solver.read_solutions((current, *elite)).numeric_matrix, copy=True)
    assert solver.step().committed
    np.testing.assert_array_equal(solver.problem.calls[-2:], [[2.], [2.]])
    np.testing.assert_array_equal(solver.read_solutions((current, *elite)).numeric_matrix, before)
    for refs in supplied_refs(solver):
        assert current in refs and elite[0] in refs
    outputs, values = output_values(solver)
    assert len(outputs) == 2
    np.testing.assert_array_equal(values, [[2.], [2.]])
    assert {ref.candidate_token for ref in outputs}.isdisjoint(
        ref.candidate_token for ref in (current, *elite))
    assert solver.solution_pool.subpool_refs("elite") == elite
    assert adapter.current_x[0] == 2.


def test_moead_pool_sources_and_operation_order_are_independent_of_native_de(monkeypatch):
    outcomes = []
    for mutate_first in (False, True):
        solver, adapter = make_solver("moead",
            partial(source_composition, mutate_first=mutate_first))
        left = add_source(solver, "left", [2.])
        right = add_source(solver, "right", [6.])
        assert solver.step().committed
        previous_members = adapter.get_population_solution_refs(solver)
        previous_values = np.array(adapter.pop_X, copy=True)

        def no_native_de(*args, **kwargs):
            raise AssertionError("an assembled change must replace native DE")

        monkeypatch.setattr(adapter, "_de_variation", no_native_de)
        assert solver.step().committed
        outputs, values = output_values(solver)
        outcomes.append(values)
        assert all(left[0] in refs and right[0] in refs for refs in supplied_refs(solver))
        np.testing.assert_array_equal(solver.read_solutions(left + right).numeric_matrix, [[2.], [6.]])
        # Accepted pool output is not a command to replace an algorithm slot.
        assert adapter.get_population_solution_refs(solver) == previous_members
        np.testing.assert_array_equal(adapter.pop_X, previous_values)
        raw, violations = solver.solution_pool.read_raw_feedback(outputs)
        np.testing.assert_array_equal(raw, np.column_stack((values[:, 0] ** 2, (values[:, 0] - 3.) ** 2)))
        np.testing.assert_array_equal(violations, [0., 0.])
    np.testing.assert_array_equal(outcomes[0], [[25.], [25.]])
    np.testing.assert_array_equal(outcomes[1], [[29.], [29.]])


@pytest.mark.parametrize("budget,accepted", [(None, (1, 3)), (3, (1,))])
def test_output_members_follow_nonprefix_admission_after_budget_cut(budget, accepted):
    solver, _ = make_solver(change=pool_random_change, batch_size=4)
    add_source(solver, "elite", [0., 1.])
    assert solver.step().committed
    if budget is not None:
        solver.register_controller(BudgetController(max_evaluations=budget))

    class OddRows:
        def select(self, candidates, feedback, context):
            return BatchDisposition(len(candidates.semantic_states), accepted)

    solver.set_evaluation_acceptance_policy(OddRows())
    assert solver.step().committed
    refs, values = output_values(solver)
    event = solver._last_evaluated_event_batch
    assert len(event.semantic_states) == (4 if budget is None else 2)
    assert tuple(ref.candidate_token for ref in refs) == tuple(event.candidate_tokens[index] for index in accepted)
    np.testing.assert_array_equal(values, event.numeric_matrix[list(accepted)])
    assert solver.solution_pool.subpool_metadata("offspring")["kind"] == "candidate_collection"


def test_rejected_batch_never_creates_requested_output():
    solver, adapter = make_solver(change=pool_random_change)
    add_source(solver, "elite", [0.])
    assert solver.step().committed
    previous_ref = adapter.get_pool_refinement_results(solver)

    class RejectAll:
        def select(self, candidates, feedback, context):
            return BatchDisposition(len(candidates.semantic_states), ())

    solver.set_evaluation_acceptance_policy(RejectAll())
    assert not solver.step().committed
    assert not solver.solution_pool.has_subpool("offspring")
    assert adapter.get_pool_refinement_results(solver) == previous_ref
    assert solver.evaluation_count == 3


def test_existing_collection_appends_over_commits_without_replacing_its_identity():
    solver, _ = make_solver()
    add_source(solver, "elite", [0.])
    solver.solution_pool.create_subpool("offspring")
    view_id = solver.solution_pool.subpool_descriptor("offspring")["view_id"]
    assert solver.step().committed
    assert solver.step().committed
    first = solver.solution_pool.subpool_refs("offspring")
    assert len(first) == 2
    assert solver.step().committed
    combined = solver.solution_pool.subpool_refs("offspring")
    assert len(combined) == 4 and combined[:2] == first
    assert solver.solution_pool.subpool_descriptor("offspring")["view_id"] == view_id


def test_post_update_failure_rolls_back_output_and_rng_then_repeats_candidates(monkeypatch):
    solver, adapter = make_solver(change=pool_random_change)
    add_source(solver, "elite", [0., 1.])
    assert solver.step().committed
    old_ref = adapter.get_pool_refinement_results(solver)
    rng_state = copy.deepcopy(adapter._operator_rng.bit_generator.state)
    original = solver._update_best

    def fail_after_algorithm_update(*args, **kwargs):
        if solver.solution_pool.has_subpool("offspring"):
            assert solver.solution_pool.subpool_refs("offspring") == ()
        raise RuntimeError("after pool output and algorithm update")

    monkeypatch.setattr(solver, "_update_best", fail_after_algorithm_update)
    with pytest.raises(RuntimeError, match="after pool output"):
        solver.step()
    failed = np.array(solver.problem.calls[-2:], copy=True)
    assert not solver.solution_pool.has_subpool("offspring")
    assert adapter._operator_rng.bit_generator.state == rng_state
    assert adapter.get_pool_refinement_results(solver) == old_ref
    monkeypatch.setattr(solver, "_update_best", original)
    assert solver.step().committed
    np.testing.assert_array_equal(solver.problem.calls[-2:], failed)
    refs, values = output_values(solver)
    assert len(refs) == 2
    np.testing.assert_array_equal(values, failed)
    assert solver.evaluation_count == 5


def test_missing_destination_fails_before_evaluation():
    solver, adapter = make_solver(change=partial(write_target, name="missing"))
    assert solver.step().committed
    old_rng = copy.deepcopy(adapter._operator_rng.bit_generator.state)
    with pytest.raises((ValueError, KeyError), match="missing|exist|target|output|subpool"):
        solver.step()
    assert len(solver.problem.calls) == 1
    assert not solver.solution_pool.has_subpool("missing")
    assert adapter._operator_rng.bit_generator.state == old_rng


@pytest.mark.parametrize("kind", ["candidate_view", "objective_projection"])
def test_owner_published_views_are_not_direct_output_destinations(kind):
    solver, adapter = make_solver(change=partial(write_target, name="owned"))
    assert solver.step().committed
    refs = adapter.get_pool_refinement_results(solver)
    if kind == "candidate_view":
        solver.solution_pool.publish_subpool_view("owned", refs, created_by=("publisher",))
    else:
        solver.solution_pool.publish_projection_subpool("owned", refs,
            created_by=("publisher",), slot=0, projection=ObjectiveProjection("weighted_sum", (1.,)))
    before = solver.solution_pool.subpool_descriptor("owned")
    with pytest.raises(ValueError, match="collection|view|projection|output|writ"):
        solver.step()
    assert len(solver.problem.calls) == 1
    assert solver.solution_pool.subpool_refs("owned") == refs
    assert solver.solution_pool.subpool_descriptor("owned") == before


def test_ancestor_destination_metadata_is_not_replayed_by_next_plain_change():
    solver, adapter = make_solver()
    add_source(solver, "elite", [0.])
    assert solver.step().committed and solver.step().committed
    refs = solver.solution_pool.subpool_refs("offspring")
    adapter.set_change(no_output_change)
    assert solver.step().committed
    assert solver.solution_pool.subpool_refs("offspring") == refs
    assert adapter.current_x[0] == 1.75


def test_recreated_destination_is_rejected_and_its_original_identity_and_unit_roll_back(monkeypatch):
    solver, adapter = make_solver(change=partial(write_target, name="offspring"))
    assert solver.step().committed
    current = adapter.get_pool_refinement_results(solver)
    solver.solution_pool.create_subpool("offspring", current)
    descriptor = solver.solution_pool.subpool_descriptor("offspring")
    before_counter = adapter._unit_counter
    before_unit = adapter.current_unit.unit_id
    before_rng = copy.deepcopy(adapter._operator_rng.bit_generator.state)
    original_update = adapter.update
    replaced_ids = []

    def recreate_after_algorithm_update(*args, **kwargs):
        original_update(*args, **kwargs)
        # A later lifecycle participant must not redirect a previously frozen
        # destination merely by reusing its human-readable name.
        solver.solution_pool.drop_subpool("offspring")
        solver.solution_pool.create_subpool("offspring", current)
        replaced_ids.append(solver.solution_pool.subpool_metadata("offspring")["view_id"])

    monkeypatch.setattr(adapter, "update", recreate_after_algorithm_update)
    with pytest.raises(ValueError, match="identity|revision|committed|target"):
        solver.step()
    assert replaced_ids and replaced_ids[0] != descriptor["view_id"]
    assert solver.solution_pool.subpool_descriptor("offspring") == descriptor
    assert solver.solution_pool.subpool_refs("offspring") == current
    assert adapter.get_pool_refinement_results(solver) == current
    assert adapter.current_unit.unit_id == before_unit
    assert adapter._unit_counter == before_counter
    assert adapter._operator_rng.bit_generator.state == before_rng
    np.testing.assert_array_equal(adapter.current_x, [4.])
    assert solver.evaluation_count == 3  # Real evaluations survive step rollback.


def test_pool_output_references_final_repaired_evaluated_version_with_the_proposal_token(monkeypatch):
    solver, adapter = make_solver(change=outside_bounds_change)
    assert solver.step().committed
    baseline = adapter.get_pool_refinement_results(solver)
    repairs = []
    original_repair = adapter.on_proposal_repair

    def observe_repair(control, repair, context):
        repairs.append(repair)
        return original_repair(control, repair, context)

    monkeypatch.setattr(adapter, "on_proposal_repair", observe_repair)
    assert solver.step().committed
    repair, = repairs
    np.testing.assert_array_equal(repair.before.numeric_matrix, [[204.], [204.]])
    np.testing.assert_array_equal(repair.after.numeric_matrix, [[100.], [100.]])
    assert repair.before.candidate_tokens == repair.after.candidate_tokens
    refs, values = output_values(solver)
    assert tuple(ref.candidate_token for ref in refs) == repair.after.candidate_tokens
    np.testing.assert_array_equal(values, repair.after.numeric_matrix)
    np.testing.assert_array_equal(solver.problem.calls[-2:], values)
    np.testing.assert_array_equal(solver._last_evaluated_event_batch.numeric_matrix, values)
    raw, violations = solver.solution_pool.read_raw_feedback(refs)
    np.testing.assert_array_equal(raw, [[10000.], [10000.]])
    np.testing.assert_array_equal(violations, [0., 0.])
    assert adapter.get_pool_refinement_results(solver) == baseline
    for ref, provenance in zip(refs, solver.solution_pool.read_provenance(refs), strict=True):
        assert provenance["metadata"]["change_outputs"]["proposal_token"] == ref.candidate_token


@pytest.mark.parametrize("kind", ["vns", "moead"])
def test_formal_checkpoint_keeps_pool_outputs_and_repeats_subsequent_change(kind, tmp_path, monkeypatch):
    monkeypatch.setenv("NSGABLACK_CHECKPOINT_HMAC_KEY", "pool-change-orchestration-test-key")
    source, source_adapter = make_solver(kind, change=pool_random_change)
    elite = add_source(source, "elite", [0., 1., 2.])
    assert source.step().committed and source.step().committed
    saved_outputs = source.solution_pool.subpool_refs("offspring")
    config = CheckpointResumeConfig(checkpoint_dir=str(tmp_path), save_on_finish=False)
    writer = CheckpointResumePlugin(config=config)
    source.add_plugin(writer)
    path = writer.save_checkpoint(reason="pool-change-orchestration")

    restored, restored_adapter = make_solver(kind, change=pool_random_change)
    reader = CheckpointResumePlugin(config=config)
    restored.add_plugin(reader)
    assert reader.resume(str(path))
    restored.run(max_steps=0)
    assert restored.problem.calls == []
    assert restored.solution_pool.subpool_refs("elite") == elite
    assert restored.solution_pool.subpool_refs("offspring") == saved_outputs
    np.testing.assert_array_equal(output_values(restored)[1], output_values(source)[1])
    before = len(source.problem.calls)
    assert source.step().committed and restored.step().committed
    np.testing.assert_array_equal(restored.problem.calls, source.problem.calls[before:])
    restored_refs, restored_values = output_values(restored)
    source_refs, source_values = output_values(source)
    assert restored_refs[:len(saved_outputs)] == source_refs[:len(saved_outputs)] == saved_outputs
    assert len(restored_refs) == len(source_refs) == len(saved_outputs) + 2
    np.testing.assert_array_equal(restored_values, source_values)
    if kind == "vns":
        np.testing.assert_array_equal(restored_adapter.current_x, source_adapter.current_x)
    else:
        np.testing.assert_array_equal(restored_adapter.pop_X, source_adapter.pop_X)
