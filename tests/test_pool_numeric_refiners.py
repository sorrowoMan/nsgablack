"""Numeric search algorithms exchange exact evaluated candidates through pool tasks."""
import copy
from dataclasses import replace

import numpy as np
import pytest
from blackbase.contracts import BatchDisposition
from blackbase.types import CandidateBatch, Feedback, UnknownState

from nsgablack.adapters import (
    GaussianSearchAdapter, GradientDescentAdapter, GradientOptimizerAdapter, MASAdapter,
    MultiStrategyConfig, PoolTaskSpec, RoleSpec, StrategyRouterAdapter,
)
from nsgablack.adapters.pool_results import PoolRefinementState
from nsgablack.adapters.subpools import adapter_path
from nsgablack.core import BlackBoxProblem, ComposableSolver, PoolRetentionPolicy
from nsgablack.core.state.pool_views import ObjectiveProjection
from nsgablack.plugins import CheckpointResumePlugin


KINDS = ("gaussian", "mas", "finite_difference", "gradient")


class Problem(BlackBoxProblem):
    def __init__(self):
        super().__init__(dimension=1, objectives=["min", "min"], bounds=[(-20., 20.)])
        self.calls = []

    def evaluate(self, candidate):
        x = float(candidate[0])
        self.calls.append(x)
        return Feedback(objectives=np.array([x*x, (x-10.)**2]), gradients=np.array([4*x-20.]))


def refiner(kind):
    if kind == "gaussian":
        return GaussianSearchAdapter(population_size=2, initialization="center", mutation_scale=.5)
    if kind == "mas":
        return MASAdapter(batch_size=2, enable_surrogate=False, random_seed=5)
    if kind == "finite_difference":
        return GradientDescentAdapter(max_directions=1, learning_rate=.1)
    return GradientOptimizerAdapter(optimizer="sgd", learning_rate=.1)


def assembled(kind, *, projected=False, mode="refine", steps=3, setup=True):
    local = refiner(kind)
    router = StrategyRouterAdapter(name="numeric", roles=[RoleSpec("local", local,
        pool_task=PoolTaskSpec("seed", mode=mode, count=1, steps=steps,
            output="output", shuffle=False))], config=MultiStrategyConfig(total_batch_size=8, adapt_weights=False))
    solver = ComposableSolver(Problem(), adapter=router)
    solver.set_random_seed(5)
    solver.set_solution_pool_retention(PoolRetentionPolicy(idle_steps=1))
    refs = solver.store_solutions(CandidateBatch.from_candidates(
        [UnknownState([8.], {"tag": "source"})], candidate_tokens=("seed-token",)))
    if projected:
        solver.solution_pool.publish_projection_subpool("numeric/seed", refs, created_by=("external",), slot=0,
            projection=ObjectiveProjection("weighted_sum", (.9, .1)))
    else:
        solver.solution_pool.create_subpool("numeric/seed", refs)
    if setup:
        solver.setup()
    return solver, local, router.units[0].adapter


@pytest.mark.parametrize("kind", KINDS)
def test_same_task_input_and_precise_result_for_numeric_algorithms(kind):
    solver, local, task = assembled(kind)
    for _ in range(3):
        assert solver.step().committed
    assert task.task_status["status"] == "done"
    assert solver.problem.calls[0] == 8.
    results = solver.solution_pool.subpools_created_by(adapter_path(solver.adapter, local))
    assert len(results) == 1
    refs = solver.solution_pool.subpool_refs(results[0])
    assert refs == local.get_pool_refinement_results(solver)
    batch = solver.read_solutions(refs)
    assert all(state.metadata["tag"] == "source" for state in batch.semantic_states)
    assert solver.solution_pool.read_raw_feedback(refs)[0].shape == (1, 2)
    assert set(refs).issubset(set(local.get_solution_pool_roots(solver)))


@pytest.mark.parametrize("kind", KINDS[:-1])
def test_projected_refinement_freezes_interpretation_and_keeps_raw_feedback(kind):
    solver, local, task = assembled(kind, projected=True)
    for _ in range(3):
        assert solver.step().committed
    assert task.task_status["status"] == "done"
    ref, = local.get_pool_refinement_results(solver)
    f, v = solver.solution_pool.read_raw_feedback((ref,))
    assert local._pool_results.best.score == pytest.approx(.9*f[0, 0] + .1*f[0, 1])
    view, = solver.solution_pool.subpools_created_by(adapter_path(solver.adapter, local))
    assert solver.solution_pool.subpool_metadata(view)["kind"] == "objective_projection"
    assert local._pool_results.best.metadata["tag"] == "source"
    assert solver.read_solutions((ref,)).semantic_states[0].as_dict()["metadata"] == local._pool_results.best.metadata


def test_objective_projection_does_not_pretend_to_transform_provider_gradients():
    solver, local, task = assembled("gradient", projected=True)
    with pytest.raises(ValueError, match="supporting objective projections"):
        solver.step()
    assert solver.problem.calls == []


@pytest.mark.parametrize("kind", KINDS)
@pytest.mark.parametrize("mode", ("initialize", "refine"))
def test_rejected_baseline_reconsumes_input_before_any_neighbor(kind, mode):
    solver, local, task = assembled(kind, mode=mode)
    class Reject:
        def select(self, candidates, feedback, context):
            return BatchDisposition(len(candidates.semantic_states), ())
    solver.set_evaluation_acceptance_policy(Reject())
    assert not solver.step().committed
    assert local.get_pool_refinement_results(solver) == ()
    solver.set_evaluation_acceptance_policy(None)
    assert solver.step().committed
    assert solver.problem.calls == [8., 8.]
    assert task.task_status["status"] == ("done" if mode == "initialize" else "running")


@pytest.mark.parametrize("kind", KINDS)
def test_update_failure_rolls_back_selection_task_and_pool_but_not_cost(kind, monkeypatch):
    solver, local, task = assembled(kind)
    assert solver.step().committed
    before, task_before = copy.deepcopy(local.get_state()), copy.deepcopy(task.get_state())
    refs, cost = local.get_pool_refinement_results(solver), solver.evaluation_count
    original = local.update
    def fail(control, candidates, feedback, context):
        original(control, candidates, feedback, context)
        raise RuntimeError("after selection")
    monkeypatch.setattr(local, "update", fail)
    with pytest.raises(RuntimeError, match="after selection"):
        solver.step()
    assert local.get_state() == before
    assert task.get_state() == task_before
    assert local.get_pool_refinement_results(solver) == refs
    assert solver.evaluation_count > cost


@pytest.mark.parametrize("kind", KINDS)
def test_checkpoint_preserves_comparison_result_and_next_search(kind):
    first, a, _ = assembled(kind)
    assert first.step().committed
    second, b, _ = assembled(kind, setup=False)
    writer, reader = CheckpointResumePlugin(), CheckpointResumePlugin()
    writer.attach(first)
    reader.attach(second)
    payload = writer._build_payload(solver=first, reason="numeric_pool")
    second.queue_restore_envelope(lambda: reader._restore_payload(solver=second, payload=payload))
    second.setup()
    second._apply_pending_restore_envelopes()
    assert a._pool_results.as_dict() == b._pool_results.as_dict()
    assert first.step().committed and second.step().committed
    np.testing.assert_allclose(first.problem.calls[1:], second.problem.calls)
    np.testing.assert_allclose(first.read_solutions(a.get_pool_refinement_results(first)).numeric_matrix,
                               second.read_solutions(b.get_pool_refinement_results(second)).numeric_matrix)


def test_finite_difference_trial_is_evaluated_instead_of_proxy_scored():
    solver, local, _ = assembled("finite_difference", steps=4)
    assert solver.step().committed
    assert solver.step().committed
    assert local.current_x[0] == 8. and local.current_score == 68.
    trial = float(local._trial_values[0])
    best, = local.get_pool_refinement_results(solver)
    assert float(solver.read_solutions((best,)).numeric_matrix[0, 0]) != trial
    assert solver.step().committed
    assert local.current_x[0] == pytest.approx(trial)
    assert local.current_score == pytest.approx(trial*trial + (trial-10.)**2)


def test_gradient_optimizer_result_is_evaluated_predecessor_not_pending_parameters():
    solver, local, _ = assembled("gradient")
    assert solver.step().committed
    ref, = local.get_pool_refinement_results(solver)
    assert solver.read_solutions((ref,)).numeric_matrix[0, 0] == 8.
    assert local.current_x[0] == pytest.approx(6.8) and local.current_score is None
    assert solver.step().committed
    assert local._pool_results.current.provenance.parent_token == ref.candidate_token


def test_one_sided_admission_cannot_fabricate_a_gradient_trial():
    solver, local, _ = assembled("finite_difference", steps=4)
    assert solver.step().committed
    class FirstOnly:
        def select(self, candidates, feedback, context):
            return BatchDisposition(len(candidates.semantic_states), (0,))
    solver.set_evaluation_acceptance_policy(FirstOnly())
    assert solver.step().committed
    assert local._trial_values is None and local.current_x[0] == 8. and local.current_score == 68.


def test_missing_exact_selected_receipt_never_falls_back_to_latest_token():
    solver, local, _ = assembled("mas")
    assert solver.step().committed
    local._pool_results.current = replace(local._pool_results.current, ref=None)
    with pytest.raises(ValueError, match="exact accepted"):
        local.get_solution_pool_roots(solver)


def test_mas_retains_and_bounds_its_actual_training_versions():
    solver, local, _ = assembled("mas", steps=4)
    local.cfg.enable_surrogate = True
    local.cfg.surrogate_max_train_samples = 2
    for _ in range(4):
        assert solver.step().committed
    assert len(local._X) == len(local._Y) == len(local._history_refs) == 2
    for row, ref in zip(local._X, local._history_refs):
        np.testing.assert_array_equal(solver.read_solutions((ref,)).numeric_matrix[0], row)
    assert set(local._history_refs).issubset(set(local.get_solution_pool_roots(solver)))


def test_mas_waits_for_training_before_surrogate_selection(monkeypatch):
    from nsgablack.utils.surrogate.vector_surrogate import VectorSurrogate

    solver, local, _ = assembled("mas", steps=3)
    local.cfg.enable_surrogate = True
    local.cfg.surrogate_min_train_samples = 3
    predictions = []
    original = VectorSurrogate.predict

    def checked_predict(model, values):
        assert local._surrogate_is_fitted()
        predictions.append(len(values))
        return original(model, values)

    monkeypatch.setattr(VectorSurrogate, "predict", checked_predict)
    assert solver.step().committed
    assert not local._surrogate_is_fitted() and not predictions
    assert solver.step().committed
    assert local._surrogate_is_fitted() and not predictions
    assert solver.step().committed
    assert predictions
