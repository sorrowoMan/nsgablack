"""Real steps join multi-child changes, exact survival and current-batch plans."""
from functools import partial
import copy

import numpy as np
import pytest
from blackbase.contracts import BatchDisposition
from blackbase.context import SnapshotIdentity

from nsgablack.adapters import (ChangeBatchResult, ChangeResult, NSGA2Adapter,
    NSGA3Adapter, SPEA2Adapter, PoolOutput)
from nsgablack.core import ComposableSolver
from nsgablack.core.control_plane import BudgetController
from nsgablack.core.state.solution_pool import SolutionRef
from nsgablack.representation import RepresentationPipeline, UniformInitializer, ClipRepair
from .test_pool_change_orchestration import RecordedProblem, make_solver, no_output_change


def pair_children(request, *, rng):
    shift = rng.uniform(.1, .2)
    children = (
        ChangeResult(request.parents[0] - shift, source_refs=request.source_refs[:1],
                     outputs=(PoolOutput("offspring", create=True),)),
        ChangeResult(request.parents[1] - 2 * shift, source_refs=request.source_refs[1:],
                     outputs=(PoolOutput("offspring", create=True),)),
    )
    return ChangeBatchResult(children[:min(2, request.max_outputs)])


def no_children(request, *, rng):
    return ChangeBatchResult()


def keep_first(pool):
    return pool.all().take(range(4))


def keep_last(pool, *, rng):
    return pool.take(range(len(pool) - 4, len(pool)))


def archive_key(pool):
    objectives, violations = pool.raw_feedback()
    return np.column_stack((violations > 0., np.maximum(0., violations), objectives.sum(axis=1)))


def archive_current(request, *, rng, capacity=3):
    # Ordinary main still contains committed records, never this sibling batch.
    assert set(request.accepted.refs).isdisjoint(request.pool.main(stage="accepted").refs)
    chosen = request.pool.subpool("elite").merge(request.accepted).top(capacity, key=archive_key)
    return (request.pool.replace_members("elite", chosen.refs),)


def bad_archive(request, *, rng):
    request.accepted.raw_feedback()
    raise RuntimeError("archive calculation failed")


def archive_output_change(request, *, rng):
    return ChangeResult(request.candidate - .1, outputs=(PoolOutput("elite"),))


def make_ga(cls=NSGA2Adapter, *, change=pair_children, selector=keep_first,
            maintenance=archive_current, offspring_size=4):
    adapter = cls(population_size=4, offspring_size=offspring_size, change=change,
        selector=selector, pool_maintenance=maintenance)
    pipeline = RepresentationPipeline(initializer=UniformInitializer(low=4., high=4.),
        repair=ClipRepair(low=-100., high=100.))
    solver = ComposableSolver(RecordedProblem(2), adapter=adapter, representation_pipeline=pipeline)
    solver.set_random_seed(83)
    solver.setup()
    solver.solution_pool.create_subpool("elite")
    return solver, adapter


def assert_manifest(solver):
    pool = solver.solution_pool
    manifest = pool.snapshots.read_verified(SnapshotIdentity.from_dict(pool.publication_ref())).data
    assert manifest["retention"]["owners"]["subpool/elite"] == [
        ref.as_dict() for ref in pool.subpool_refs("elite")]
    assert manifest["subpool_metadata"]["elite"] == pool.subpool_metadata("elite")


@pytest.mark.parametrize("cls", [NSGA2Adapter, NSGA3Adapter, SPEA2Adapter])
def test_complete_change_and_pool_survival_share_real_feedback_without_extra_evaluations(cls):
    solver, adapter = make_ga(cls)
    assert solver.step().committed
    parents = adapter.get_population_solution_refs(solver)
    first = solver.solution_pool.subpool_descriptor("elite")
    assert solver.step().committed
    assert solver.evaluation_count == len(solver.problem.calls) == 8
    # The explicit survivor rule keeps parents; the separate archive can retain
    # a superior admitted child even though the algorithm did not retain it.
    assert adapter.get_population_solution_refs(solver) == parents
    elite = solver.solution_pool.subpool_refs("elite")
    assert set(elite).isdisjoint(parents)
    outputs = solver.solution_pool.subpool_refs("offspring")
    assert len(outputs) == len({ref.candidate_token for ref in outputs}) == 4
    assert set(elite).issubset(outputs)
    assert solver.solution_pool.subpool_descriptor("elite")["view_id"] == first["view_id"]
    assert solver.solution_pool.subpool_descriptor("elite")["revision"] == first["revision"] + 1
    assert_manifest(solver)


def test_complete_change_runs_once_per_pair_and_replaces_native_crossover(monkeypatch):
    solver, adapter = make_ga(offspring_size=3)
    assert solver.step().committed
    calls = []
    operation = adapter.get_bound_change()
    original = operation.change

    def record(request, *, rng):
        calls.append(request.max_outputs)
        return original(request, rng=rng)

    def forbidden(*args, **kwargs):
        raise AssertionError("native crossover ran after complete change")

    monkeypatch.setattr(operation, "change", record)
    monkeypatch.setattr(adapter, "_crossover", forbidden)
    assert solver.step().committed
    assert calls == [3, 1]
    assert solver.evaluation_count == 7
    provenance = solver._last_evaluated_event_provenance
    for index, item in enumerate(provenance):
        declared = tuple(SolutionRef.from_dict(ref) for ref in item.metadata["change_source_refs"])
        assert len(declared) == 1
        assert declared[0] in tuple(SolutionRef.from_dict(ref) for ref in item.metadata["change_input_refs"])


@pytest.mark.parametrize("budget,indices", [(None, (1, 3)), (3, (1,))])
def test_nonprefix_acceptance_and_budget_preserve_children_and_current_archive(budget, indices):
    solver, adapter = make_ga()
    assert solver.step().committed
    baseline = set(solver.solution_pool.select(stage="accepted"))
    if budget is not None:
        solver.register_controller(BudgetController(max_evaluations=solver.evaluation_count + budget))

    class Rows:
        def select(self, candidates, feedback, context):
            return BatchDisposition(len(candidates.semantic_states), indices)

    solver.set_evaluation_acceptance_policy(Rows())
    assert solver.step().committed
    event = solver._last_evaluated_event_batch
    outputs = solver.solution_pool.subpool_refs("offspring")
    assert tuple(ref.candidate_token for ref in outputs) == tuple(event.candidate_tokens[i] for i in indices)
    assert set(solver.solution_pool.subpool_refs("elite")).difference(baseline) == set(outputs)
    assert len(solver.problem.calls) == 4 + (4 if budget is None else 3)
    assert_manifest(solver)


def test_empty_change_is_idle_and_does_not_publish_maintenance():
    solver, adapter = make_ga(change=no_children)
    assert solver.step().committed
    before = solver.solution_pool.subpool_descriptor("elite")
    manifest = solver.solution_pool.publication_ref()
    outcome = solver.step()
    assert outcome.status == "idle" and not outcome.committed
    assert solver.evaluation_count == 4
    assert solver.solution_pool.publication_ref() == manifest
    assert solver.solution_pool.subpool_descriptor("elite") == before


def test_pool_return_selection_uses_exact_versions_even_with_equal_values():
    # Existing identity-aware selection must not reverse-match four equal rows.
    solver, adapter = make_ga(change=None, selector=keep_last, maintenance=None)
    assert solver.step().committed
    previous = adapter.get_population_solution_refs(solver)
    assert len({ref.candidate_token for ref in previous}) == 4
    assert solver.step().committed
    current = adapter.get_population_solution_refs(solver)
    assert set(previous).isdisjoint(current)
    assert tuple(ref.candidate_token for ref in current) == solver._last_evaluated_event_batch.candidate_tokens


@pytest.mark.parametrize("kind", ["vns", "moead"])
def test_trajectory_and_slot_replacement_maintain_once_per_real_update(kind, monkeypatch):
    solver, adapter = make_solver(kind, change=no_output_change)
    adapter.set_pool_maintenance(archive_current)
    solver.solution_pool.create_subpool("elite")
    calls = []
    operation = adapter.get_bound_operator("pool_maintenance")
    original = operation.maintain

    def record(request, *, rng):
        calls.append(request)
        return original(request, rng=rng)

    monkeypatch.setattr(operation, "maintain", record)
    assert solver.step().committed
    assert len(calls) == 1  # Includes VNS baseline and MOEA/D bootstrap.
    assert solver.step().committed
    assert len(calls) == 2
    for request in calls:
        with pytest.raises(RuntimeError, match="ended"):
            request.accepted.values
    assert_manifest(solver)


def test_maintenance_failure_restores_unit_rng_pool_and_manifest_but_keeps_cost(monkeypatch):
    solver, adapter = make_ga()
    assert solver.step().committed
    before_rng = copy.deepcopy(adapter._rng.bit_generator.state)
    descriptor = solver.solution_pool.subpool_descriptor("elite")
    members = solver.solution_pool.subpool_refs("elite")
    manifest = solver.solution_pool.publication_ref()
    operation = adapter.get_bound_operator("pool_maintenance")
    with monkeypatch.context() as patched:
        patched.setattr(operation, "maintain", bad_archive)
        with pytest.raises(RuntimeError, match="archive calculation failed"):
            solver.step()
    assert solver.evaluation_count == 8
    assert solver.solution_pool.publication_ref() == manifest
    assert solver.solution_pool.subpool_descriptor("elite") == descriptor
    assert solver.solution_pool.subpool_refs("elite") == members
    assert adapter._rng.bit_generator.state == before_rng
    assert solver.step().committed
    np.testing.assert_array_equal(solver.problem.calls[4:8], solver.problem.calls[8:12])
    assert_manifest(solver)


def test_same_target_output_and_maintenance_fail_before_membership_publication():
    solver, adapter = make_ga(change=archive_output_change)
    assert solver.step().committed
    before = solver.solution_pool.subpool_descriptor("elite")
    manifest = solver.solution_pool.publication_ref()
    with pytest.raises(ValueError, match="append and replace"):
        solver.step()
    assert solver.solution_pool.subpool_descriptor("elite") == before
    assert solver.solution_pool.publication_ref() == manifest
