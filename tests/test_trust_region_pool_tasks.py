"""Trust-region regions consume pool seeds and deliver exact evaluated versions."""
import copy
from dataclasses import replace

import numpy as np
import pytest
from blackbase.contracts import BatchDisposition
from blackbase.types import CandidateBatch, UnknownState

from nsgablack.adapters import (
    MOEADAdapter, MultiStrategyConfig, PoolTaskSpec, RoleSpec,
    StrategyRouterAdapter, TrustRegionDFOAdapter, TrustRegionMODFOAdapter,
    TrustRegionNonSmoothAdapter, TrustRegionSubspaceAdapter, subpools,
)
from nsgablack.adapters.subpools import adapter_path
from nsgablack.core import BlackBoxProblem, ComposableSolver, PoolRetentionPolicy
from nsgablack.core.evaluation_feedback import OptimizationFeedbackBatch, copy_feedback_with_result
from nsgablack.core.state.pool_views import ObjectiveProjection
from nsgablack.context_keys import KEY_MO_WEIGHTS
from nsgablack.plugins import CheckpointResumePlugin
from nsgablack.representation import RepresentationPipeline


KINDS = ("dfo", "mo", "nonsmooth", "subspace")
CLASSES = dict(zip(KINDS, (TrustRegionDFOAdapter, TrustRegionMODFOAdapter,
                         TrustRegionNonSmoothAdapter, TrustRegionSubspaceAdapter)))


class Problem(BlackBoxProblem):
    def __init__(self, dimension=1):
        super().__init__(dimension=dimension, objectives=["min", "min"], bounds=[(-100., 100.)] * dimension)
        self.calls = []

    def evaluate(self, candidate):
        self.calls.append(np.asarray(candidate).copy())
        return [np.sum(np.asarray(candidate)**2), np.sum((np.asarray(candidate)-10.)**2)]


class Initializer:
    def __init__(self, start=8., dimension=1):
        self.start, self.dimension = start, dimension

    def initialize(self, problem, context):
        return np.full(self.dimension, self.start)


def refiner(kind, **kwargs):
    options = dict(batch_size=3, initial_radius=1., random_seed=11)
    if kind == "subspace":
        options.update(subspace_dim=1, min_samples=2, sample_limit=6)
    options.update(kwargs)
    return CLASSES[kind](**options)


def standalone(kind, *, start=8., dimension=1, **kwargs):
    adapter = refiner(kind, **kwargs)
    solver = ComposableSolver(Problem(dimension), adapter=adapter,
        representation_pipeline=RepresentationPipeline(initializer=Initializer(start, dimension)))
    solver.set_random_seed(13)
    solver.setup()
    return solver, adapter


def projected(kind, *, steps=2, setup=True):
    source = MOEADAdapter(name="directions", population_size=2, batch_size=2,
                          neighborhood_size=2, decomposition="weighted_sum")
    adapter = refiner(kind)
    router = StrategyRouterAdapter(name="trust_refine", roles=[RoleSpec("source", source),
        RoleSpec("local", adapter, pool_task=PoolTaskSpec(subpools.all(source),
            steps=steps, output="results", shuffle=False))],
        config=MultiStrategyConfig(total_batch_size=8, adapt_weights=False,
            phase_policy=lambda context: "source" if context["step"] == 0 else "refine",
            phase_roles={"source": ["source"], "refine": ["local"]}))
    solver = ComposableSolver(Problem(), adapter=router,
        representation_pipeline=RepresentationPipeline(initializer=Initializer()))
    solver.set_random_seed(13)
    solver.set_solution_pool_retention(PoolRetentionPolicy(idle_steps=1))
    if setup:
        solver.setup()
        assert solver.step().committed
    return solver, adapter, router.units[1].adapter


@pytest.mark.parametrize("kind", KINDS)
def test_baseline_precedes_region_and_rejection_retries_exact_seed(kind):
    solver, adapter = standalone(kind)

    class Reject:
        def select(self, candidates, feedback, context):
            return BatchDisposition(len(candidates.semantic_states), ())

    solver.set_evaluation_acceptance_policy(Reject())
    assert not solver.step().committed
    assert adapter._best_score is None and adapter.get_pool_refinement_results(solver) == ()
    solver.set_evaluation_acceptance_policy(None)
    assert solver.step().committed
    assert len(solver.problem.calls) == 2
    np.testing.assert_array_equal(solver.problem.calls, [[8.], [8.]])
    assert adapter._radius == 1.
    result, = adapter.get_pool_refinement_results(solver)
    np.testing.assert_array_equal(solver.read_solutions((result,)).numeric_matrix, [[8.]])
    assert solver.step().committed
    assert len(solver.problem.calls) == 5


@pytest.mark.parametrize("kind", KINDS)
def test_projected_tasks_reuse_the_same_assembly_and_publish_raw_results(kind):
    solver, adapter, task = projected(kind)
    for _ in range(4):
        assert solver.step().committed
    assert task.task_status["status"] == "done"
    names = solver.solution_pool.projection_subpools(adapter_path(solver.adapter, adapter))
    assert len(names) == 2
    for name in names:
        refs = solver.solution_pool.subpool_refs(name)
        assert len(refs) == 1
        x = solver.read_solutions(refs).numeric_matrix[:, 0]
        objectives, _ = solver.solution_pool.read_raw_feedback(refs)
        np.testing.assert_allclose(objectives, np.stack((x*x, (x-10.)**2), axis=1))
    if kind == "mo":
        assert adapter._weights is None  # External task frame supersedes native weights.


@pytest.mark.parametrize("kind", KINDS)
@pytest.mark.parametrize("mode", ("initialize", "refine"))
@pytest.mark.parametrize("reject_first", (False, True))
def test_named_native_pool_modes_use_explicit_seed_and_freeze_native_frame(kind, mode, reject_first):
    adapter = refiner(kind)
    router = StrategyRouterAdapter(roles=[RoleSpec("local", adapter,
        pool_task=PoolTaskSpec("seeds", mode=mode, steps=2, output="results", shuffle=False))])
    solver = ComposableSolver(Problem(), adapter=router,
        representation_pipeline=RepresentationPipeline(initializer=Initializer(99.)))
    solver.setup()
    source, = solver.store_solutions(CandidateBatch.from_candidates([[7.]], candidate_tokens=("supplied",)))
    solver.solution_pool.create_subpool(f"{router.name}/seeds", (source,))
    if reject_first:
        class Reject:
            def select(self, candidates, feedback, context):
                return BatchDisposition(len(candidates.semantic_states), ())
        solver.set_evaluation_acceptance_policy(Reject())
        assert not solver.step().committed
        assert adapter._pool_results.current is None
        solver.set_evaluation_acceptance_policy(None)
    assert solver.step().committed
    np.testing.assert_array_equal(adapter._center, [7.])
    assert adapter._pool_input_task and adapter._pool_results.projection is None
    weights = None if kind != "mo" else adapter._weights.copy()
    assert solver.step().committed
    if weights is not None:
        np.testing.assert_array_equal(adapter._weights, weights)
    assert router.units[0].adapter.task_status["status"] == "done"
    result, = adapter.get_pool_refinement_results(solver)
    assert result in adapter.get_solution_pool_roots(solver)


@pytest.mark.parametrize("kind", KINDS)
def test_projection_frame_checkpoint_and_next_decision(kind):
    source, first, _ = projected(kind, steps=3)
    assert source.step().committed
    assert source.step().committed
    target, second, _ = projected(kind, steps=3, setup=False)
    writer, reader = CheckpointResumePlugin(), CheckpointResumePlugin()
    writer.attach(source)
    reader.attach(target)
    payload = writer._build_payload(solver=source, reason="trust_region")
    target.queue_restore_envelope(lambda: reader._restore_payload(solver=target, payload=payload))
    target.setup()
    target._apply_pending_restore_envelopes()
    assert first.get_state() == second.get_state()
    assert source.step().committed and target.step().committed
    np.testing.assert_array_equal(first._center, second._center)
    assert first._best_score == second._best_score and first._radius == second._radius
    np.testing.assert_array_equal(source.read_solutions(first.get_pool_refinement_results(source)).numeric_matrix,
                                  target.read_solutions(second.get_pool_refinement_results(target)).numeric_matrix)


@pytest.mark.parametrize("kind", KINDS)
def test_changed_projection_rejected_without_mutating_the_task(kind):
    solver, adapter, _ = projected(kind)
    assert solver.step().committed
    before = copy.deepcopy(adapter.get_state())
    weights = (.25, .75)
    changed = ObjectiveProjection("weighted_sum", weights).apply(
        OptimizationFeedbackBatch.from_arrays([[64., 4.]], [0.]))
    with pytest.raises(ValueError, match="projection changed"):
        adapter.update(solver, [adapter._center.copy()], changed, {})
    assert adapter.get_state() == before


@pytest.mark.parametrize("kind", KINDS)
def test_projected_seed_rejection_keeps_pool_input_available(kind):
    solver, adapter, task = projected(kind)

    class Reject:
        def select(self, candidates, feedback, context):
            return BatchDisposition(len(candidates.semantic_states), ())

    solver.set_evaluation_acceptance_policy(Reject())
    assert not solver.step().committed
    rejected = solver.problem.calls[-1].copy()
    assert adapter._best_score is None
    solver.set_evaluation_acceptance_policy(None)
    assert solver.step().committed
    np.testing.assert_array_equal(solver.problem.calls[-1], rejected)
    assert adapter._radius == 1.


@pytest.mark.parametrize("kind", KINDS)
def test_wrong_exact_ref_rejected_before_installing_center(kind, monkeypatch):
    solver, adapter = standalone(kind)
    wrong, = solver.store_solutions(CandidateBatch.from_candidates([[99.]], candidate_tokens=("wrong",)))
    original = adapter.update

    def corrupt(control, candidates, feedback, context):
        items = [replace(item, info={**item.info, "accepted_solution_ref": wrong.as_dict()}) for item in feedback.items]
        original(control, candidates, OptimizationFeedbackBatch.from_feedback(items), context)

    monkeypatch.setattr(adapter, "update", corrupt)
    with pytest.raises(ValueError, match="candidate token"):
        solver.step()
    assert adapter._best_score is None and adapter.get_pool_refinement_results(solver) == ()


@pytest.mark.parametrize("kind", KINDS)
def test_baseline_repair_can_establish_center_but_neighbors_must_stay_in_region(kind):
    solver, adapter = standalone(kind)

    class Shift:
        def repair(self, candidate, context):
            return np.asarray(candidate) + 10.

    solver.representation_pipeline = RepresentationPipeline(initializer=Initializer(), repair=Shift())
    assert solver.step().committed
    # Pipeline initialization and proposal admission are separate repair stages.
    np.testing.assert_array_equal(adapter._center, solver.problem.calls[-1])
    assert adapter._center[0] > 8. + adapter._radius
    before = copy.deepcopy(adapter.get_state())
    with pytest.raises(ValueError, match="outside the trust region"):
        solver.step()
    assert len(solver.problem.calls) == 1
    assert adapter.get_state() == before


@pytest.mark.parametrize("kind", KINDS)
def test_failed_selection_restores_region_results_samples_and_rng(kind, monkeypatch):
    solver, adapter, _ = projected(kind)
    assert solver.step().committed
    before = copy.deepcopy(adapter.get_state())
    original = adapter.update

    def fail(*args, **kwargs):
        original(*args, **kwargs)
        raise RuntimeError("after trust selection")

    monkeypatch.setattr(adapter, "update", fail)
    with pytest.raises(RuntimeError, match="after trust selection"):
        solver.step()
    assert adapter.get_state() == before
    assert solver.solution_pool.projection_subpools(adapter_path(solver.adapter, adapter)) == ()
    monkeypatch.setattr(adapter, "update", original)
    assert solver.step().committed


@pytest.mark.parametrize("kind", KINDS)
def test_partial_admission_retains_exact_candidate_metadata_and_identity(kind, monkeypatch):
    solver, adapter = standalone(kind)
    seed = UnknownState([8.], {"domain": "seed"})
    refs = solver.store_solutions(CandidateBatch.from_candidates([seed], candidate_tokens=("source",)))
    # Exercise explicit ordinary initialize through the formal input cursor.
    from nsgablack.context_keys import KEY_SOLUTION_INPUT_REF
    key = solver.solution_pool.bind_input(refs)
    original = adapter.propose
    monkeypatch.setattr(adapter, "propose", lambda c, ctx: original(c, {**ctx, KEY_SOLUTION_INPUT_REF: key}))
    assert solver.step().committed
    baseline, = adapter.get_pool_refinement_results(solver)
    monkeypatch.setattr(adapter, "propose", original)
    monkeypatch.setattr(adapter, "_sample_delta", lambda c, ctx: np.array([-1.]))

    class LastOnly:
        def select(self, candidates, feedback, context):
            return BatchDisposition(len(candidates.semantic_states), (2,))

    solver.set_evaluation_acceptance_policy(LastOnly())
    assert solver.step().committed
    selected = adapter._pool_results.current
    assert selected.ref != baseline
    assert selected.provenance.parent_token == baseline.candidate_token
    stored = solver.read_solutions((selected.ref,)).semantic_states[0]
    assert stored.metadata["domain"] == "seed"
    np.testing.assert_array_equal(stored.values, adapter._center)


@pytest.mark.parametrize("kind", KINDS)
def test_projection_preserves_negative_scores_and_feasibility_order(kind, monkeypatch):
    solver, adapter = standalone(kind, start=0., include_center=False)
    monkeypatch.setattr(adapter, "_sample_delta", lambda c, ctx: np.ones(1))
    original = adapter.update
    infeasible = [False]

    def project(control, candidates, feedback, context):
        items = [copy_feedback_with_result(item, objectives=[-1. - float(np.asarray(candidates[i])[0])],
            violation=1. if infeasible[0] else 0.) for i, item in enumerate(feedback.items)]
        values = ObjectiveProjection("weighted_sum", (1.,)).apply(OptimizationFeedbackBatch.from_feedback(items))
        original(control, candidates, values, context)

    monkeypatch.setattr(adapter, "update", project)
    assert solver.step().committed
    assert solver.step().committed
    np.testing.assert_array_equal(adapter._center, [1.])
    best, = adapter.get_pool_refinement_results(solver)
    infeasible[0] = True
    assert solver.step().committed
    assert adapter.get_pool_refinement_results(solver) == (best,)
    np.testing.assert_array_equal(adapter._center, [1.])


def test_native_mo_rescores_old_center_when_ordinary_direction_changes(monkeypatch):
    solver, adapter = standalone("mo", start=8., include_center=False)
    original = adapter.update
    weights = [[1., 0.]]
    monkeypatch.setattr(adapter, "update", lambda c, x, f, ctx: original(c, x, f, {**ctx, KEY_MO_WEIGHTS: weights[0]}))
    assert solver.step().committed
    assert adapter._best_score == 64.
    monkeypatch.setattr(adapter, "_sample_delta", lambda c, ctx: np.array([-1.]))
    weights[0] = [0., 1.]
    assert solver.step().committed
    # x=7 has new score 9: worse than center=8's new score 4, although
    # comparing to the previous direction's scalar 64 would accept it.
    np.testing.assert_array_equal(adapter._center, [8.])
    assert adapter._best_score == 4.


def test_native_mo_pool_task_freezes_weights_and_restart_releases_frame():
    solver, adapter = standalone("mo")
    adapter._pool_input_task = True
    f = np.array([[1., 3.]])
    first = adapter._get_weights(solver, {}, f).copy()
    np.testing.assert_array_equal(adapter._get_weights(solver, {}, f), first)
    with pytest.raises(ValueError, match="weights changed"):
        adapter._get_weights(solver, {KEY_MO_WEIGHTS: [1., 0.]}, f)
    adapter.restart_search(solver, {})
    np.testing.assert_array_equal(adapter._get_weights(solver, {KEY_MO_WEIGHTS: [1., 0.]}, f), [1., 0.])


def test_subspace_uses_retained_task_samples_and_bounded_roots(monkeypatch):
    solver, adapter = standalone("subspace", dimension=2, basis_method="pca", resample_every=1,
                                 min_samples=2, sample_limit=4)
    solver.set_solution_pool_retention(PoolRetentionPolicy(idle_steps=1))
    assert solver.step().committed
    assert solver.step().committed
    captured = []
    original = adapter._build_basis_from_population
    monkeypatch.setattr(adapter, "_build_basis_from_population", lambda x, c: (captured.append(x.copy()), original(x, c))[1])
    expected = solver.read_solutions(adapter._sample_refs).numeric_matrix.copy()
    assert solver.step().committed
    np.testing.assert_array_equal(captured[0], expected)
    assert len(adapter._sample_refs) == 4
    assert set(adapter._sample_refs).issubset(adapter.get_solution_pool_roots(solver))
    solver.read_solutions(adapter._sample_refs)
    adapter.restart_search(solver, {})
    assert adapter._sample_refs == () and adapter.get_solution_pool_roots(solver) == ()


def test_subspace_bound_clipping_keeps_candidate_inside_span():
    solver, adapter = standalone("subspace", dimension=2)
    solver.problem.bounds = [(0., 1.), (0., 1.)]
    adapter._center = np.array([.9, .5])
    adapter._basis = np.array([[1.], [1.]]) / np.sqrt(2.)
    point = adapter._clip_to_bounds(adapter._center + np.array([.5, .5]), solver)
    np.testing.assert_allclose(point, [1., .6])
    assert adapter._repair_within_region(point)
