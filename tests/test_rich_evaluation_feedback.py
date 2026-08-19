from __future__ import annotations

import numpy as np
from blackbase.state_ref import StateRef
from blackbase.types import Feedback, UnknownState

from nsgablack.adapters.algorithm_adapter import AlgorithmAdapter, CompositeAdapter
from nsgablack.adapters.gradient_optimizer import (
    GradientOptimizerAdapter,
    GradientOptimizerConfig,
)
from blackbase.evaluation import (
    StateMaterializationResult,
    StateTransitionResult,
)
from nsgablack.core.base import BlackBoxProblem
from nsgablack.core.composable_solver import ComposableSolver
from nsgablack.core.evaluation_feedback import OptimizationFeedbackBatch


class _RichProblem(BlackBoxProblem):
    def __init__(self, *, objectives=None) -> None:
        super().__init__(
            name="rich-feedback",
            dimension=2,
            bounds={"x0": (-2.0, 2.0), "x1": (-2.0, 2.0)},
            objectives=objectives or ["loss"],
        )

    def evaluate(self, candidate):
        x = np.asarray(candidate, dtype=float).reshape(-1)
        loss = float(np.sum(x * x))
        return Feedback(
            objectives=np.array([loss], dtype=float),
            gradients=2.0 * x,
            loss=loss,
            metrics={"mae": float(np.mean(np.abs(x)))},
            signals={"provider": "autograd"},
        )


class _RecordingAdapter(AlgorithmAdapter):
    def __init__(self, name: str = "recording", candidates=None) -> None:
        super().__init__(name=name)
        self.candidates = list(
            candidates
            or (
                np.array([0.5, -0.25], dtype=float),
                np.array([1.0, 0.5], dtype=float),
            )
        )
        self.feedback = None

    def propose(self, control, context):
        _ = (control, context)
        return [candidate.copy() for candidate in self.candidates]

    def update(self, control, candidates, feedback, context):
        _ = (control, candidates, context)
        self.feedback = feedback


def test_problem_feedback_reaches_adapter_without_losing_ml_fields():
    adapter = _RecordingAdapter()
    solver = ComposableSolver(problem=_RichProblem(), adapter=adapter)

    solver.step()

    assert isinstance(adapter.feedback, OptimizationFeedbackBatch)
    objectives, violations = adapter.feedback
    assert objectives.shape == (2, 1)
    assert violations.shape == (2,)
    assert np.allclose(adapter.feedback.items[0].gradients, [1.0, -0.5])
    assert adapter.feedback.items[0].loss == objectives[0, 0]
    assert adapter.feedback.items[0].metrics["mae"] == 0.375
    assert adapter.feedback.items[0].signals["provider"] == "autograd"


def test_feedback_batch_subset_preserves_semantic_items():
    items = (
        Feedback(
            objectives=np.array([1.0]),
            gradients=np.array([10.0, 11.0]),
            metrics={"row": 0},
        ),
        Feedback(
            objectives=np.array([2.0]),
            gradients=np.array([20.0, 21.0]),
            metrics={"row": 1},
        ),
        Feedback(
            objectives=np.array([3.0]),
            gradients=np.array([30.0, 31.0]),
            metrics={"row": 2},
        ),
    )
    batch = OptimizationFeedbackBatch.from_feedback(items)

    selected = batch.subset([2, 0])

    assert np.allclose(selected.objectives[:, 0], [3.0, 1.0])
    assert selected.items[0].metrics["row"] == 2
    assert np.allclose(selected.items[1].gradients, [10.0, 11.0])


def test_composite_adapter_routes_rich_feedback_by_proposal_range():
    first = _RecordingAdapter("first", [np.array([0.0, 0.0])])
    second = _RecordingAdapter(
        "second",
        [np.array([1.0, 1.0]), np.array([2.0, 2.0])],
    )
    composite = CompositeAdapter([first, second])
    candidates = composite.propose(object(), {})
    batch = OptimizationFeedbackBatch.from_feedback(
        (
            Feedback(objectives=np.array([0.0]), metrics={"owner": "first"}),
            Feedback(objectives=np.array([2.0]), metrics={"owner": "second-0"}),
            Feedback(objectives=np.array([8.0]), metrics={"owner": "second-1"}),
        )
    )

    composite.update(object(), candidates, batch, {})

    assert isinstance(first.feedback, OptimizationFeedbackBatch)
    assert first.feedback.items[0].metrics["owner"] == "first"
    assert [item.metrics["owner"] for item in second.feedback.items] == [
        "second-0",
        "second-1",
    ]


def test_population_provider_may_return_feedback_items():
    class _Provider:
        name = "rich-provider"
        semantic_mode = "equivalent"

        def can_handle_individual(self, solver, x, context):
            _ = (solver, x, context)
            return False

        def evaluate_individual(self, solver, x, context, individual_id=None):
            _ = (solver, x, context, individual_id)
            raise AssertionError("individual provider path should not run")

        def can_handle_population(self, solver, population, context):
            _ = (solver, population, context)
            return True

        def evaluate_population(self, solver, population, context):
            _ = (solver, context)
            return [
                Feedback(
                    objectives=np.array([float(np.sum(row * row))]),
                    gradients=2.0 * row,
                    metrics={"batch": True},
                )
                for row in np.asarray(population, dtype=float)
            ]

    solver = ComposableSolver(problem=_RichProblem())
    solver.register_evaluation_provider(_Provider())
    population = np.array([[0.25, 0.5], [1.0, -1.0]], dtype=float)

    objectives, violations = solver.evaluate_population(population)
    batch = solver.get_last_feedback_batch()

    assert objectives.shape == (2, 1)
    assert np.allclose(violations, 0.0)
    assert isinstance(batch, OptimizationFeedbackBatch)
    assert np.allclose(batch.items[1].gradients, [2.0, -2.0])
    assert batch.items[1].metrics["batch"] is True


def test_two_objective_tuple_remains_an_objective_vector():
    class _TupleProblem(_RichProblem):
        def __init__(self) -> None:
            super().__init__(objectives=["f1", "f2"])

        def evaluate(self, candidate):
            x = np.asarray(candidate, dtype=float).reshape(-1)
            return float(x[0] ** 2), float(x[1] ** 2)

    solver = ComposableSolver(problem=_TupleProblem())

    objectives, violation = solver.evaluate_individual(np.array([2.0, 3.0]))

    assert np.allclose(objectives, [4.0, 9.0])
    assert violation == 0.0


def test_fresh_run_clears_previous_rich_feedback():
    solver = ComposableSolver(problem=_RichProblem())
    solver.evaluate_population(np.array([[0.5, 0.25]], dtype=float))
    assert solver.get_last_feedback_batch() is not None

    solver.prepare_fresh_run()

    assert solver.get_last_feedback_batch() is None


def test_gradient_optimizer_consumes_provider_gradient_without_ml_backend_imports():
    adapter = GradientOptimizerAdapter(
        GradientOptimizerConfig(optimizer="sgd", learning_rate=0.1)
    )
    adapter.current_x = np.array([1.0, -1.0], dtype=float)
    solver = ComposableSolver(problem=_RichProblem(), adapter=adapter)

    solver.step()

    assert np.allclose(adapter.current_x, [0.8, -0.8])
    assert adapter.last_gradient_norm == np.linalg.norm([2.0, -2.0])
    assert adapter.step_index == 1


def test_gradient_optimizer_fails_closed_when_provider_omits_gradient():
    adapter = GradientOptimizerAdapter(
        GradientOptimizerConfig(optimizer="adam", learning_rate=0.01)
    )
    adapter.current_x = np.array([0.5, 0.5], dtype=float)
    adapter._proposal_pending = True
    legacy = OptimizationFeedbackBatch.from_arrays([[0.5]], [0.0])

    try:
        adapter.update(
            object(),
            [np.array([0.5, 0.5])],
            legacy,
            {},
        )
    except ValueError as exc:
        assert "requires one Feedback item with gradients" in str(exc)
    else:
        raise AssertionError("missing gradients must not silently fall back")


def test_gradient_optimizer_has_stable_method_ids():
    config = GradientOptimizerConfig.from_method(
        "gradient.adamw",
        learning_rate=5e-4,
        weight_decay=1e-2,
    )

    assert config.optimizer == "adamw"
    assert config.learning_rate == 5e-4


def test_gradient_optimizer_consumes_ml_unknown_state_and_feedback_sequence():
    class _MlControl:
        def init_candidate(self, context):
            _ = context
            return UnknownState([1.0, -1.0], metadata={"source": "ml"})

        def repair_candidate(self, candidate, context):
            _ = context
            assert isinstance(candidate, UnknownState)
            return candidate

    adapter = GradientOptimizerAdapter(
        GradientOptimizerConfig(optimizer="sgd", learning_rate=0.1)
    )
    control = _MlControl()
    adapter.setup(control)

    proposed = adapter.propose(control, {})
    adapter.update(
        control,
        proposed,
        (Feedback(objectives=[2.0], gradients=[2.0, -2.0]),),
        {},
    )

    population = adapter.get_population()
    assert population is not None
    assert isinstance(population[0], UnknownState)
    assert np.allclose(population[0].as_array(), [0.8, -0.8])
    assert population[0].metadata["optimizer_method"] == "gradient.sgd"


def test_feedback_projection_preserves_provider_gradient_ref():
    ref = StateRef(
        provider_id="gradient-provider/v1",
        state_id="gradient-1",
        state_kind="gradient",
    )
    batch = OptimizationFeedbackBatch.from_feedback(
        (Feedback(objectives=[1.0], gradient_ref=ref),)
    )

    assert batch.items[0].gradient_ref == ref


def test_provider_transition_materialization_still_passes_representation_repair():
    parameter_ref = StateRef(
        provider_id="gradient-provider/v1",
        state_id="parameters-1",
        state_kind="model_parameters",
        scope_id="run-1",
        device="cpu",
    )
    gradient_ref = StateRef(
        provider_id="gradient-provider/v1",
        state_id="gradient-1",
        state_kind="gradient",
        scope_id="run-1",
        device="cpu",
    )

    class _Gateway:
        def transition(self, request, resource_context):
            _ = resource_context
            return StateTransitionResult(
                request_id=request.request_id,
                method_id=request.method_id,
                status="applied",
                state_ref=request.state_ref.next_version(),
            )

        def materialize(self, request, resource_context):
            _ = resource_context
            return StateMaterializationResult(
                request_id=request.request_id,
                state_ref=request.state_ref,
                target=request.target,
                value=UnknownState([5.0, -5.0], metadata={"provider": True}),
            )

    class _Control:
        def repair_candidate(self, candidate, context):
            _ = context
            assert isinstance(candidate, UnknownState)
            return candidate.with_values(np.clip(candidate.as_array(), -1.0, 1.0))

    adapter = GradientOptimizerAdapter(
        GradientOptimizerConfig(optimizer="sgd", learning_rate=0.1),
        state_gateway=_Gateway(),
        prefer_provider_transition=True,
    )
    adapter.current_x = np.asarray([0.0, 0.0], dtype=float)
    adapter._candidate_kind = "unknown_state"
    adapter._proposal_pending = True
    adapter.update(
        _Control(),
        (UnknownState([0.0, 0.0]),),
        (
            Feedback(
                objectives=[1.0],
                gradients=[1.0, 1.0],
                gradient_ref=gradient_ref,
                info={"evaluation_state_ref": parameter_ref},
            ),
        ),
        {},
    )

    assert np.allclose(adapter.current_x, [1.0, -1.0])
