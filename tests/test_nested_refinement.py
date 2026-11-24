"""Recursive search views preserve winners, comparison frames and raw evidence."""
import copy

import numpy as np
import pytest

from examples.cases.solution_pool.cases.moead_refinement.adapter.refinement import (
    build_nested_refinement_adapter,
)
from examples.cases.solution_pool.cases.moead_refinement.build_solver import build_solver
from nsgablack.adapters.subpools import adapter_path
from nsgablack.core import BlackBoxProblem, ComposableSolver
from nsgablack.core.evaluation_feedback import OptimizationFeedbackBatch
from nsgablack.core.state.pool_views import ObjectiveProjection
from nsgablack.core.state.solution_pool import SolutionRef
from nsgablack.representation import RepresentationPipeline


class Delivery(BlackBoxProblem):
    def __init__(self):
        super().__init__(dimension=1, objectives=["min", "min"], bounds=[(-20., 20.)])

    def evaluate(self, candidate):
        x = float(candidate[0])
        return [x*x, (x-10.)**2]


class DecreasingRoutes:
    context_requires = ("vns_k",)

    def initialize(self, problem, context):
        return np.array([8.])

    def mutate(self, candidate, context):
        return candidate - 1.


def _deterministic_solver(*, setup=True):
    router = build_nested_refinement_adapter(directions=4, view_count=None,
        local_steps=2, fine_steps=2, decomposition="weighted_sum")
    solver = ComposableSolver(Delivery(), adapter=router,
        representation_pipeline=RepresentationPipeline(
            initializer=DecreasingRoutes(), mutator=DecreasingRoutes()))
    solver.set_random_seed(37)
    if setup:
        solver.setup()
    return solver


def _worker(solver, role):
    return next(unit.adapter for unit in solver.adapter.units if unit.role == role)


def _views(solver, role):
    return solver.solution_pool.projection_subpools(
        adapter_path(solver.adapter, _worker(solver, role).inner))


def _until(solver, condition, *, limit=30):
    for _ in range(limit):
        if condition():
            return
        assert solver.step().committed
    pytest.fail("nested refinement did not reach its expected phase")


def _raw(solver, refs):
    x = solver.solution_pool.read(refs).numeric_matrix[:, 0]
    return np.stack([x*x, (x-10.)**2], axis=1)


def test_fine_search_starts_from_coarse_winner_and_improves_its_direction():
    solver = _deterministic_solver()
    fine = _worker(solver, "fine")
    _until(solver, lambda: fine.task_status["status"] == "running")
    pool = solver.solution_pool
    coarse_views = _views(solver, "coarse")
    assert len(coarse_views) == 4
    job = fine._local["jobs"][0]
    assert job["source_view"] in coarse_views
    winner = pool.subpool_refs(job["source_view"])
    assert len(winner) == 1
    np.testing.assert_array_equal(fine.inner.current_x,
                                  pool.read(winner).numeric_matrix[0])
    assert fine._local["jobs"][0]["ref"] == winner[0].as_dict()
    projection = ObjectiveProjection.from_dict(job["projection"])
    expected = projection.apply(OptimizationFeedbackBatch.from_arrays(_raw(solver, winner), [0.]))
    assert fine.inner.current_score == pytest.approx(expected.objectives[0, 0])
    assert fine.inner._projection_frame == job["projection"]

    # The direction minimizing x² accepts x-1, while the direction minimizing
    # (x-10)² rejects it. Both must export their final incumbent, not last trial.
    first_weight = lambda name: pool.subpool_metadata(name)["projection"]["weights"][0]
    improving = max(coarse_views, key=first_weight)
    rejecting = min(coarse_views, key=first_weight)
    coarse_improved_x = pool.read(pool.subpool_refs(improving)).numeric_matrix[0, 0]
    parent = pool.subpool_metadata(rejecting)["parent"]
    original = next(job for job in _worker(solver, "coarse")._local["jobs"]
                    if job["source_view"] == parent["name"])
    rejected_winner = pool.subpool_refs(rejecting)[0]
    # The baseline is a local proposal derived from the seed; verify that a
    # rejected x-1 trial never becomes the delivered incumbent.
    original_ref = SolutionRef.from_dict(original["ref"])
    np.testing.assert_array_equal(pool.read((rejected_winner,)).numeric_matrix,
                                  pool.read((original_ref,)).numeric_matrix)

    _until(solver, lambda: fine.task_status["status"] == "done")
    final = next(name for name in _views(solver, "fine")
                 if pool.subpool_metadata(name)["parent"]["name"] == improving)
    fine_x = pool.read(pool.subpool_refs(final)).numeric_matrix[0, 0]
    assert fine_x == pytest.approx(coarse_improved_x - 1.)
    assert fine_x*fine_x < coarse_improved_x*coarse_improved_x

    # Fine output remains raw, and MOEA/D runs its own replacement comparison.
    _until(solver, lambda: _worker(solver, "moead").task_status["status"] == "done")
    refs = pool.subpool_refs("nested_directions/refined")
    values, _ = pool.read_raw_feedback(refs)
    np.testing.assert_allclose(values, _raw(solver, refs))
    producer = _worker(solver, "moead").inner
    np.testing.assert_allclose(producer.pop_F,
        np.stack([producer.pop_X[:, 0]**2, (producer.pop_X[:, 0]-10.)**2], axis=1))


def test_standard_nested_case_keeps_lineage_projection_and_shared_candidate_versions():
    solver = build_solver(dict(directions=4, view_count=2, local_steps=2, fine_steps=2,
                               nested_refinement=True, max_steps=12))
    solver.run()
    pool = solver.solution_pool
    assert all(_worker(solver, role).task_status["status"] == "done"
               for role in ("coarse", "fine", "moead", "ga"))
    assert len(_views(solver, "coarse")) == len(_views(solver, "fine")) == 2
    for name in _views(solver, "fine"):
        metadata = pool.subpool_metadata(name)
        parent = metadata["parent"]
        coarse = pool.subpool_metadata(parent["name"])
        assert metadata["projection"] == coarse["projection"]
        assert parent["view_id"] == coarse["view_id"]
        assert len(parent["ancestors"]) == 1
        direction = parent["ancestors"][0]
        assert direction["view_id"] == coarse["parent"]["view_id"]
        refs = pool.subpool_refs(name)
        assert len(refs) == 1
        # View membership references the same pool record in the aggregate.
        assert refs[0] in pool.subpool_refs("nested_directions/refined")
        assert pool.read_raw_feedback(refs)[0].shape == (1, 2)
    assert _worker(solver, "moead").inner.pop_F.shape == (4, 2)


def test_checkpoint_resumes_second_level_with_same_frozen_parent_and_projection():
    from nsgablack.plugins import CheckpointResumePlugin

    source = _deterministic_solver()
    _until(source, lambda: _worker(source, "fine").task_status["status"] == "running")
    target = _deterministic_solver(setup=False)
    writer, reader = CheckpointResumePlugin(), CheckpointResumePlugin()
    writer.attach(source)
    reader.attach(target)
    payload = writer._build_payload(solver=source, reason="nested_projection")
    target.queue_restore_envelope(lambda: reader._restore_payload(solver=target, payload=payload))
    target.setup()
    target._apply_pending_restore_envelopes()
    jobs = copy.deepcopy(_worker(source, "fine")._local["jobs"])
    assert _worker(target, "fine")._local["jobs"] == jobs
    assert _worker(source, "fine").inner._projection_frame == _worker(target, "fine").inner._projection_frame
    for solver in (source, target):
        _until(solver, lambda: _worker(solver, "fine").task_status["status"] == "done")
    for a, b in zip(_views(source, "fine"), _views(target, "fine")):
        first, second = source.solution_pool, target.solution_pool
        assert first.subpool_metadata(a)["parent"] == second.subpool_metadata(b)["parent"]
        np.testing.assert_array_equal(first.read(first.subpool_refs(a)).numeric_matrix,
                                      second.read(second.subpool_refs(b)).numeric_matrix)
