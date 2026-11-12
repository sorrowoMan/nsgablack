"""Providers deliver measured feedback; control owns Bias, admission and count."""
import numpy as np
import pytest

from blackbase.preferences import PreferenceDelta
from blackbase.types import CandidateBatch
from nsgablack.adapters import AlgorithmAdapter
from nsgablack.core import BlackBoxProblem, ComposableSolver, FeasibleEvaluationAcceptance
from nsgablack.core.evaluation_feedback import OptimizationFeedbackBatch
from nsgablack.plugins import (
    BroydenSolverProviderPlugin, MultiFidelityEvaluationConfig,
    MultiFidelityEvaluationProviderPlugin, NewtonSolverProviderPlugin,
    NumericalSolverConfig, SurrogateEvaluationConfig, SurrogateEvaluationProviderPlugin,
)


class Problem(BlackBoxProblem):
    def __init__(self):
        super().__init__(dimension=1, objectives=["cost"], bounds=[(-2.0, 2.0)])

    def evaluate(self, candidate):
        return [2.0]

    def evaluate_constraints(self, candidate):
        return [5.0]

    def evaluate_low_fidelity(self, candidate):
        return [1.0]

    def build_implicit_system(self, candidate, context):
        return {"residual": lambda y: np.asarray(y) - 2.0,
                "jacobian": lambda y: np.ones((1, 1)), "x0": np.array([0.5])}

    def evaluate_from_implicit_solution(self, candidate, solution, context):
        return [float(solution[0])]

    def evaluate_constraints_from_implicit_solution(self, candidate, solution, context):
        return [5.0]


class Preference:
    preference_keys = ("objectives.0",)

    def __init__(self):
        self.contexts = []

    def preferences(self, candidate, feedback, context):
        self.contexts.append(context)
        return (PreferenceDelta("objectives.0", 3.0, "nonzero selection preference"),)


class Fixed(AlgorithmAdapter):
    def __init__(self):
        super().__init__(name="raw_provider_boundary")
        self.updated = False

    def propose(self, control, context):
        return [np.array([0.0]), np.array([1.0])]

    def update(self, control, candidates, feedback, context):
        self.updated = True


class Surrogate:
    def __init__(self):
        self.training = []

    def fit(self, x, y):
        self.training.append(np.array(y, copy=True))

    def predict(self, x):
        return np.full((len(x), 1), 2.0)

    def uncertainty(self, x):
        return np.full((len(x), 1), 0.25)


def control(owner, *, allow_approximate=True, problem=None):
    bias = Preference()
    solver = ComposableSolver(Problem() if problem is None else problem, adapter=Fixed(), bias_module=bias,
        ignore_constraint_violation_when_bias=True,
        evaluation_acceptance_policy=FeasibleEvaluationAcceptance())
    solver.configure_evaluation_policy(allow_approximate=allow_approximate)
    solver.add_plugin(owner)
    return solver, bias


def assert_raw_gate(feedback, candidates):
    assert np.allclose(feedback.raw_violations, 5.0)
    assert np.allclose(feedback.violations, 0.0)
    disposition = FeasibleEvaluationAcceptance().select(
        CandidateBatch.from_candidates(candidates), feedback, {})
    assert disposition.accepted_indices == ()


def test_surrogate_warmup_and_prediction_project_bias_once_and_count_dispatches():
    model = Surrogate()
    owner = SurrogateEvaluationProviderPlugin(surrogate=model, config=SurrogateEvaluationConfig(
        min_train_samples=2, min_true_evals=1, topk_exploit=1, topk_explore=0))
    solver, bias = control(owner)
    solver.evaluate_population(np.array([[0.0], [1.0]]))
    warmup = solver.get_last_feedback_batch()
    assert np.allclose(warmup.raw_objectives, 2.0)
    assert np.allclose(warmup.objectives, 5.0)
    assert_raw_gate(warmup, [[0.0], [1.0]])
    solver.evaluate_population(np.array([[-1.0], [0.0], [0.5], [1.0]]))
    predicted = solver.get_last_feedback_batch()
    assert np.allclose(predicted.raw_objectives, 2.0)
    assert np.allclose(predicted.objectives, 5.0)
    assert_raw_gate(predicted, [[-1.0], [0.0], [0.5], [1.0]])
    assert solver.evaluation_count == len(bias.contexts) == 6
    assert owner.stats == {"true_evals": 3, "surrogate_calls": 1, "train_samples": 3}
    assert solver.problem.evaluation_count == 3
    assert all(np.allclose(y, 2.0) for y in model.training)
    assert [item.info["evaluation_fidelity"] for item in predicted.items] == ["true", "surrogate", "surrogate", "surrogate"]
    assert all(context["metrics"]["surrogate_std"] == 0.25 for context in bias.contexts[-4:])


def test_default_surrogate_claims_batch_without_constructing_until_dispatch(monkeypatch):
    from nsgablack.utils.surrogate import vector_surrogate
    model = Surrogate()
    created = []
    def make_model(**kwargs):
        created.append(kwargs)
        return model
    monkeypatch.setattr(vector_surrogate, "VectorSurrogate", make_model)
    owner = SurrogateEvaluationProviderPlugin(config=SurrogateEvaluationConfig(
        min_train_samples=2, min_true_evals=1, topk_exploit=1, topk_explore=0))
    solver, _ = control(owner)
    provider = solver.evaluation_mediator.list_providers()[0]
    assert provider.can_handle_population(solver, np.array([[0.0], [1.0]]), {})
    assert created == [] and model.training == []
    solver.evaluate_population(np.array([[0.0], [1.0]]))
    assert len(created) == len(model.training) == 1
    assert created[0] == {"num_objectives": 1, "model_type": "rf"}
    assert owner.stats["true_evals"] == 2
    solver.evaluate_population(np.array([[0.0]]))
    assert len(created) == 1
    assert len(model.training) == 2


def test_parallel_surrogate_failure_is_not_silently_replayed_serially():
    attempted = []
    failure = RuntimeError("parallel evaluation interrupted")
    class Parallel:
        def evaluate_population(self, values, **kwargs):
            attempted.append(np.array(values, copy=True))
            raise failure
    owner = SurrogateEvaluationProviderPlugin(surrogate=Surrogate(),
        parallel_evaluator=Parallel(), config=SurrogateEvaluationConfig(min_train_samples=2))
    solver, bias = control(owner)
    with pytest.raises(RuntimeError, match="parallel evaluation interrupted") as caught:
        solver.evaluate_population(np.array([[0.0], [1.0]]))
    assert caught.value is failure
    assert len(attempted) == 1
    assert solver.problem.evaluation_count == 0
    assert solver.evaluation_count == 2
    assert bias.contexts == []


def test_parallel_true_subset_violations_return_to_exact_original_rows():
    class FeasibleProblem(Problem):
        def evaluate_constraints(self, candidate):
            return [0.0]
    class RankedModel(Surrogate):
        def predict(self, x):
            return np.array([[8.0], [1.0], [6.0]])
    class Parallel:
        def evaluate_population(self, values, **kwargs):
            assert values.tolist() == [[1.0]]
            return np.array([[9.0]]), np.array([11.0])
    owner = SurrogateEvaluationProviderPlugin(surrogate=RankedModel(), online_training=False,
        parallel_evaluator=Parallel(), config=SurrogateEvaluationConfig(
            min_train_samples=0, min_true_evals=1, topk_exploit=1, topk_explore=0))
    solver, _ = control(owner, problem=FeasibleProblem())
    candidates = [[0.0], [1.0], [-1.0]]
    solver.evaluate_population(np.array(candidates))
    feedback = solver.get_last_feedback_batch()
    assert feedback.raw_objectives[:, 0].tolist() == [8.0, 9.0, 6.0]
    assert feedback.raw_violations.tolist() == [0.0, 11.0, 0.0]
    assert feedback.violations.tolist() == [0.0, 0.0, 0.0]
    assert feedback.items[1].info["raw_evaluation"]["constraint_violation"] == 11.0
    assert [item.info["evaluation_fidelity"] for item in feedback.items] == ["surrogate", "true", "surrogate"]
    disposition = FeasibleEvaluationAcceptance().select(CandidateBatch.from_candidates(candidates), feedback, {})
    assert disposition.accepted_indices == (0, 2)
    assert owner.stats["true_evals"] == 1
    assert solver.evaluation_count == 3


def test_multifidelity_is_explicitly_approximate_preserves_raw_rows_and_counts():
    owner = MultiFidelityEvaluationProviderPlugin(config=MultiFidelityEvaluationConfig(
        min_high_fidelity=1, topk_exploit=1, topk_explore=0))
    solver, bias = control(owner)
    solver.evaluate_population(np.array([[-1.0], [0.0], [0.5], [1.0]]))
    feedback = solver.get_last_feedback_batch()
    assert owner.create_provider().semantic_mode == "approximate"
    assert feedback.raw_objectives[:, 0].tolist() == [2.0, 1.0, 1.0, 1.0]
    assert feedback.objectives[:, 0].tolist() == [5.0, 4.0, 4.0, 4.0]
    assert_raw_gate(feedback, [[-1.0], [0.0], [0.5], [1.0]])
    assert [item.info["evaluation_fidelity"] for item in feedback.items] == ["high", "low", "low", "low"]
    assert owner.stats == {"low_calls": 4, "high_calls": 1}
    assert solver.evaluation_count == len(bias.contexts) == 4
    assert solver.problem.evaluation_count == 1


def test_fully_pretrained_zero_true_policy_does_not_call_problem_or_fit():
    class Pretrained(Surrogate):
        def fit(self, x, y):
            pytest.fail("pretrained provider must not fit")

        def predict(self, x):
            return np.full((len(x), 1), 7.0)

    owner = SurrogateEvaluationProviderPlugin(surrogate=Pretrained(), online_training=False,
        config=SurrogateEvaluationConfig(min_train_samples=0, min_true_evals=0,
            topk_exploit=0, topk_explore=0, retrain_every_call=False))
    solver, bias = control(owner)
    solver.evaluate_population(np.array([[-1.0], [0.0], [1.0]]))
    feedback = solver.get_last_feedback_batch()
    assert feedback.raw_objectives[:, 0].tolist() == [7.0] * 3
    assert feedback.objectives[:, 0].tolist() == [10.0] * 3
    assert solver.problem.evaluation_count == owner.stats["true_evals"] == 0
    assert owner.stats["train_samples"] == 0
    assert solver.evaluation_count == len(bias.contexts) == 3
    assert [item.info["evaluation_fidelity"] for item in feedback.items] == ["surrogate"] * 3


def test_multifidelity_cannot_bypass_default_approximation_gate():
    owner = MultiFidelityEvaluationProviderPlugin()
    solver, bias = control(owner, allow_approximate=False)
    with pytest.warns(RuntimeWarning, match="allow_approximate=False"):
        solver.evaluate_population(np.array([[0.0], [1.0]]))
    assert owner.stats == {"low_calls": 0, "high_calls": 0}
    assert solver.evaluation_count == solver.problem.evaluation_count == len(bias.contexts) == 2
    assert np.allclose(solver.get_last_feedback_batch().raw_objectives, 2.0)


@pytest.mark.parametrize("kind", [NewtonSolverProviderPlugin, BroydenSolverProviderPlugin])
@pytest.mark.parametrize("batch", [False, True])
def test_numerical_solver_preserves_raw_constraints_and_feedback_metrics(kind, batch):
    owner = kind(config=NumericalSolverConfig(fallback_to_problem_eval=False, warn_on_failure=False))
    solver, bias = control(owner)
    if batch:
        solver.evaluate_population(np.array([[0.0], [1.0]]))
        feedback = solver.get_last_feedback_batch()
        candidates = [[0.0], [1.0]]
    else:
        solver.evaluate_individual(np.array([0.0]))
        feedback = OptimizationFeedbackBatch.from_feedback((solver._last_individual_feedback,))
        candidates = [[0.0]]
    assert np.allclose(feedback.raw_objectives, 2.0)
    assert np.allclose(feedback.objectives, 5.0)
    assert_raw_gate(feedback, candidates)
    assert solver.evaluation_count == len(bias.contexts) == len(candidates)
    assert owner.stats["success"] == owner.stats["calls"] == len(candidates)
    assert solver.problem.evaluation_count == 0
    assert all(context["metrics"]["implicit_success"] == 1.0 for context in bias.contexts)
    assert all(item.metrics["implicit_residual"] < 1e-8 for item in feedback.items)


@pytest.mark.parametrize("kind", [NewtonSolverProviderPlugin, BroydenSolverProviderPlugin])
def test_numerical_explicit_exception_fallback_keeps_control_projection(kind, monkeypatch):
    owner = kind(config=NumericalSolverConfig(fallback_to_problem_eval=True, warn_on_failure=False))
    solver, bias = control(owner)
    def fail(**kwargs):
        raise RuntimeError("backend unavailable")
    monkeypatch.setattr(owner, "solve_backend", fail)
    solver.evaluate_individual(np.array([0.0]))
    feedback = OptimizationFeedbackBatch.from_feedback((solver._last_individual_feedback,))
    assert np.allclose(feedback.raw_objectives, 2.0)
    assert np.allclose(feedback.objectives, 5.0)
    assert_raw_gate(feedback, [[0.0]])
    assert solver.evaluation_count == len(bias.contexts) == 1
    assert owner.stats["fallback"] == solver.problem.evaluation_count == 1


@pytest.mark.parametrize("owner", [
    SurrogateEvaluationProviderPlugin(surrogate=Surrogate(), online_training=False,
        config=SurrogateEvaluationConfig(min_train_samples=0, min_true_evals=0, topk_exploit=0, topk_explore=0)),
    MultiFidelityEvaluationProviderPlugin(),
    NewtonSolverProviderPlugin(config=NumericalSolverConfig(fallback_to_problem_eval=False)),
    BroydenSolverProviderPlugin(config=NumericalSolverConfig(fallback_to_problem_eval=False)),
])
def test_real_step_rejects_raw_infeasibility_even_with_softened_selection(owner):
    solver, _ = control(owner)
    outcome = solver.step()
    assert outcome.status == "rejected"
    assert outcome.evaluations == solver.evaluation_count == 2
    assert not solver.adapter.updated
