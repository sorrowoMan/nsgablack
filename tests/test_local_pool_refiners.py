"""Single-trajectory algorithms share pool tasks without losing their decisions."""
import copy
from dataclasses import replace

import numpy as np
import pytest

from blackbase.contracts import BatchDisposition
from blackbase.types import CandidateBatch
from nsgablack.adapters import (
    MOEADAdapter, MultiStrategyConfig, PatternSearchAdapter, PoolTaskSpec,
    RoleSpec, SimulatedAnnealingAdapter, SingleTrajectoryAdaptiveAdapter,
    StrategyRouterAdapter, subpools,
)
from nsgablack.adapters.pool_results import PoolRefinementState
from nsgablack.adapters.subpools import adapter_path
from nsgablack.core import BlackBoxProblem, ComposableSolver, PoolRetentionPolicy
from nsgablack.core.evaluation_feedback import OptimizationFeedbackBatch
from nsgablack.core.state.pool_views import ObjectiveProjection
from nsgablack.plugins import CheckpointResumePlugin
from nsgablack.representation import RepresentationPipeline


KINDS = ("sa", "pattern", "trajectory")


class Problem(BlackBoxProblem):
    def __init__(self):
        super().__init__(dimension=1, objectives=["min", "min"], bounds=[(-100., 100.)])
        self.calls = []

    def evaluate(self, candidate):
        x = float(candidate[0])
        self.calls.append(x)
        return [x * x, (x - 10.) ** 2]


class Operator:
    context_requires = ("generation",)

    def __init__(self, start=8., delta=-1.):
        self.start, self.delta, self.mutations = start, delta, 0

    def initialize(self, problem, context):
        return np.array([self.start])

    def mutate(self, candidate, context):
        self.mutations += 1
        return candidate + self.delta


def refiner(kind):
    if kind == "sa":
        return SimulatedAnnealingAdapter(batch_size=2, random_seed=3,
            initial_temperature=1e20, objective_aggregation="first")
    if kind == "pattern":
        return PatternSearchAdapter(step_size=1., objective_aggregation="first")
    return SingleTrajectoryAdaptiveAdapter(batch_size=2, accept_worse_prob=1.,
        restart_patience=1000, objective_aggregation="first")


def standalone(kind, *, start=8., delta=-1.):
    adapter, operator = refiner(kind), Operator(start, delta)
    solver = ComposableSolver(Problem(), adapter=adapter,
        representation_pipeline=RepresentationPipeline(initializer=operator, mutator=operator))
    solver.set_random_seed(13)
    solver.setup()
    return solver, adapter, operator


def projected(kind, *, steps=2, setup=True):
    source = MOEADAdapter(name="directions", population_size=2, batch_size=2,
                          neighborhood_size=2, decomposition="weighted_sum")
    local = refiner(kind)
    router = StrategyRouterAdapter(name="local_pool", roles=[
        RoleSpec("source", source),
        RoleSpec("local", local, pool_task=PoolTaskSpec(subpools.all(source),
            steps=steps, output="results", shuffle=False)),
    ], config=MultiStrategyConfig(total_batch_size=8, adapt_weights=False,
        phase_policy=lambda context: "source" if context["step"] == 0 else "refine",
        phase_roles={"source": ["source"], "refine": ["local"]}))
    operator = Operator()
    solver = ComposableSolver(Problem(), adapter=router,
        representation_pipeline=RepresentationPipeline(initializer=operator, mutator=operator))
    solver.set_random_seed(13)
    solver.set_solution_pool_retention(PoolRetentionPolicy(idle_steps=1))
    if setup:
        solver.setup()
        assert solver.step().committed  # Publish the lazy MOEA/D initialization.
    return solver, local, router.units[1].adapter


@pytest.mark.parametrize("kind", KINDS)
def test_initial_point_is_evaluated_before_neighbors(kind):
    solver, adapter, operator = standalone(kind)
    assert solver.step().committed
    assert solver.problem.calls == [8.]
    assert operator.mutations == 0
    assert adapter.current_score == 64.
    result, = adapter.get_pool_refinement_results(solver)
    np.testing.assert_array_equal(solver.read_solutions((result,)).numeric_matrix, [[8.]])
    assert solver.step().committed
    assert len(solver.problem.calls) > 1


@pytest.mark.parametrize("kind", KINDS)
def test_rejected_baseline_does_not_install_score_or_result(kind):
    solver, adapter, operator = standalone(kind)

    class Reject:
        def select(self, candidates, feedback, context):
            return BatchDisposition(len(candidates.semantic_states), ())

    solver.set_evaluation_acceptance_policy(Reject())
    assert not solver.step().committed
    assert adapter.current_score is None
    assert adapter.get_pool_refinement_results(solver) == ()
    solver.set_evaluation_acceptance_policy(None)
    assert solver.step().committed
    assert solver.problem.calls == [8., 8.] and operator.mutations == 0


@pytest.mark.parametrize("kind", ("sa", "trajectory"))
def test_uphill_exploration_returns_task_best_and_retains_both_versions(kind):
    solver, adapter, _ = standalone(kind, start=0., delta=10.)
    solver.set_solution_pool_retention(PoolRetentionPolicy(idle_steps=1))
    assert solver.step().committed
    original, = adapter.get_pool_refinement_results(solver)
    assert solver.step().committed
    np.testing.assert_array_equal(adapter.current_x, [10.])
    assert adapter.get_pool_refinement_results(solver) == (original,)
    roots = adapter.get_solution_pool_roots(solver)
    assert len(roots) == 2 and original in roots
    assert {0., 10.} == set(solver.read_solutions(roots).numeric_matrix[:, 0])
    # A later publication of the same token does not retarget the selected ref.
    solver.store_solutions(CandidateBatch.from_candidates([[99.]], candidate_tokens=(original.candidate_token,)))
    assert adapter.get_pool_refinement_results(solver) == (original,)


@pytest.mark.parametrize("kind", KINDS)
def test_same_projected_pool_task_runs_every_refiner_and_preserves_raw_results(kind):
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
        f, _ = solver.solution_pool.read_raw_feedback(refs)
        np.testing.assert_allclose(f, np.stack((x*x, (x-10.)**2), axis=1))
        assert solver.solution_pool.subpool_metadata(name)["parent"] is not None


@pytest.mark.parametrize("kind", KINDS)
def test_projection_frame_cannot_change_without_restart(kind):
    solver, adapter, _ = projected(kind, steps=3)
    assert solver.step().committed
    before = adapter._pool_results.as_dict()
    frame = before["projection"]
    weights = (.25, .75) if frame["weights"] != [.25, .75] else (.75, .25)
    changed = ObjectiveProjection("weighted_sum", weights).apply(
        OptimizationFeedbackBatch.from_arrays([[64., 4.]], [0.]))
    with pytest.raises(ValueError, match="projection changed"):
        adapter.update(solver, [adapter.current_x.copy()], changed, {})
    assert adapter._pool_results.as_dict() == before


@pytest.mark.parametrize("kind", KINDS)
def test_projected_checkpoint_retains_exact_result_frame_and_next_decision(kind):
    source, first, _ = projected(kind, steps=3)
    assert source.step().committed
    target, second, _ = projected(kind, steps=3, setup=False)
    writer, reader = CheckpointResumePlugin(), CheckpointResumePlugin()
    writer.attach(source)
    reader.attach(target)
    payload = writer._build_payload(solver=source, reason="local_pool")
    target.queue_restore_envelope(lambda: reader._restore_payload(solver=target, payload=payload))
    target.setup()
    target._apply_pending_restore_envelopes()
    assert first._pool_results.as_dict() == second._pool_results.as_dict()
    assert source.step().committed and target.step().committed
    np.testing.assert_array_equal(first.current_x, second.current_x)
    assert first.current_score == second.current_score
    np.testing.assert_array_equal(
        source.read_solutions(first.get_pool_refinement_results(source)).numeric_matrix,
        target.read_solutions(second.get_pool_refinement_results(target)).numeric_matrix)


@pytest.mark.parametrize("kind", KINDS)
def test_failed_update_restores_current_best_and_result_view(kind, monkeypatch):
    solver, adapter, task = projected(kind)
    assert solver.step().committed
    before = adapter._pool_results.as_dict()
    original = adapter.update

    def fail(*args, **kwargs):
        original(*args, **kwargs)
        raise RuntimeError("after local selection")

    monkeypatch.setattr(adapter, "update", fail)
    with pytest.raises(RuntimeError, match="after local selection"):
        solver.step()
    assert adapter._pool_results.as_dict() == before
    assert solver.solution_pool.projection_subpools(adapter_path(solver.adapter, adapter)) == ()
    monkeypatch.setattr(adapter, "update", original)
    assert solver.step().committed


@pytest.mark.parametrize("kind", KINDS)
def test_accepted_ref_for_a_different_candidate_is_rejected(kind, monkeypatch):
    solver, adapter, _ = standalone(kind)
    wrong, = solver.store_solutions(CandidateBatch.from_candidates([[99.]], candidate_tokens=("wrong",)))
    original = adapter.update

    def corrupt(control, candidates, feedback, context):
        items = [replace(item, info={**item.info, "accepted_solution_ref": wrong.as_dict()})
                 for item in feedback.items]
        modified = OptimizationFeedbackBatch.from_feedback(items, violations=feedback.violations,
                                                           metadata=feedback.metadata)
        original(control, candidates, modified, context)

    monkeypatch.setattr(adapter, "update", corrupt)
    with pytest.raises(ValueError, match="candidate token"):
        solver.step()
    assert adapter.current_score is None
    assert adapter.get_pool_refinement_results(solver) == ()


def test_projected_comparison_never_trades_feasibility_for_large_objective_gain():
    state = PoolRefinementState()
    feedback = ObjectiveProjection("weighted_sum", (1.,)).apply(
        OptimizationFeedbackBatch.from_arrays([[1e20], [-1e20]], [0., 1.]))
    scores, violations = state.scores(feedback, lambda f, v: f[:, 0] + 1e6*v)
    assert state.key(scores[0], violations[0]) < state.key(scores[1], violations[1])


def test_projected_restore_requires_exact_refs_and_frame():
    solver, adapter, _ = projected("sa")
    assert solver.step().committed
    value = copy.deepcopy(adapter._pool_results.as_dict())
    value["current"]["ref"] = None
    with pytest.raises(ValueError, match="exact accepted"):
        PoolRefinementState.from_dict(value)


@pytest.mark.parametrize("kind", KINDS)
def test_partial_admission_tracks_the_delivered_candidate_and_parent(kind):
    solver, adapter, _ = standalone(kind)
    assert solver.step().committed
    baseline, = adapter.get_pool_refinement_results(solver)

    class SecondOnly:
        def select(self, candidates, feedback, context):
            return BatchDisposition(len(candidates.semantic_states), (1,))

    solver.set_evaluation_acceptance_policy(SecondOnly())
    assert solver.step().committed
    selected = adapter._pool_results.current
    # In one dimension PatternSearch's second direction is the negative poll.
    assert selected.ref != baseline
    assert selected.provenance.parent_token == baseline.candidate_token
    np.testing.assert_array_equal(solver.read_solutions((selected.ref,)).numeric_matrix[0], adapter.current_x)


@pytest.mark.parametrize("kind", KINDS)
def test_projected_refiner_rejects_infeasible_objective_bargains(kind, monkeypatch):
    solver, adapter, _ = standalone(kind, start=0., delta=10.)
    original = adapter.update

    def project(control, candidates, feedback, context):
        # All neighbors have a huge apparent gain and violate the constraint.
        # Delivery identity remains the exact evaluated candidate's identity.
        from nsgablack.core.evaluation_feedback import copy_feedback_with_result
        items = [copy_feedback_with_result(item,
            objectives=[1e20 if float(np.asarray(candidates[i])[0]) == 0 else -1e20],
            violation=0. if float(np.asarray(candidates[i])[0]) == 0 else 1.)
            for i, item in enumerate(feedback.items)]
        values = OptimizationFeedbackBatch.from_feedback(items)
        original(control, candidates, ObjectiveProjection("weighted_sum", (1.,)).apply(values), context)

    monkeypatch.setattr(adapter, "update", project)
    assert solver.step().committed
    best, = adapter.get_pool_refinement_results(solver)
    assert solver.step().committed
    np.testing.assert_array_equal(adapter.current_x, [0.])
    assert adapter.get_pool_refinement_results(solver) == (best,)
