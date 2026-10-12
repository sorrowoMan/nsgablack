import numpy as np
import pytest

from blackbase.preferences import PreferenceDelta
from blackbase.types import CandidateBatch, Feedback
from nsgablack.adapters import AlgorithmAdapter
from nsgablack.core import BlackBoxProblem, ComposableSolver, FeasibleEvaluationAcceptance
from nsgablack.core.evaluation_feedback import OptimizationFeedbackBatch
from nsgablack.core.solver_helpers import EVALUATION_EVENT_KEY
from nsgablack.plugins import EvaluationModelConfig, EvaluationModelProviderPlugin


class Problem(BlackBoxProblem):
    def __init__(self):
        super().__init__(dimension=1, objectives=["minimize"], bounds=[(-10, 10)])

    def evaluate(self, candidate):
        return Feedback(objectives=[2.], info={"constraint_violation": max(0., float(candidate[0]))})


class Preference:
    preference_keys = ("objectives.0",)

    def preferences(self, candidate, feedback, context):
        return (PreferenceDelta("objectives.0", -.5, "selection preference"),)


class Proposer(AlgorithmAdapter):
    def __init__(self):
        super().__init__(name="bias_boundary")
        self.updated = None

    def propose(self, control, context):
        return [np.array([-.5]), np.array([5.])]

    def update(self, control, candidates, feedback, context):
        self.updated = np.asarray(candidates).copy()


def build(provider=False):
    solver = ComposableSolver(Problem(), adapter=Proposer(), bias_module=Preference(),
                              ignore_constraint_violation_when_bias=True,
                              evaluation_acceptance_policy=FeasibleEvaluationAcceptance())
    if provider:
        class Backend:
            def solve(self, request):
                return {"status": "ok", "objective": 2., "violation": 5.}
        solver.register_evaluation_provider(EvaluationModelProviderPlugin(
            config=EvaluationModelConfig(scope="outer", warn_on_failure=False),
            backend_factory=lambda problem, context: Backend(),
        ).create_provider())
        solver.problem.evaluate = lambda candidate: pytest.fail("provider must short-circuit Problem")
    return solver


@pytest.mark.parametrize("provider", [False, True])
@pytest.mark.parametrize("batch", [False, True])
def test_raw_feasibility_survives_bias_in_single_batch_and_provider_paths(provider, batch):
    solver = build(provider)
    candidates = CandidateBatch.from_candidates([[5.]], candidate_tokens=("candidate",))
    if batch:
        _, violations = solver.evaluate_population(np.array([[5.]]))
        feedback = solver.get_last_feedback_batch()
    else:
        _, violation = solver.evaluate_individual(np.array([5.]))
        violations = [violation]
        feedback = OptimizationFeedbackBatch.from_feedback((solver._last_individual_feedback,))
    assert np.allclose(violations, 0.)
    restored = OptimizationFeedbackBatch.from_dict(feedback.as_dict())
    assert restored.raw_violations.tolist() == [5.]
    disposition = FeasibleEvaluationAcceptance().select(candidates, restored, {})
    assert disposition.accepted_indices == ()
    assert disposition.metadata["constraint_view"] == "raw_evaluation"


@pytest.mark.parametrize("provider", [False, True])
def test_real_step_admission_and_durable_event_agree_on_raw_constraint(provider):
    solver = build(provider)
    outcome = solver.step()
    assert outcome.evaluations == 2
    if provider:
        assert outcome.status == "rejected"
        assert solver.adapter.updated is None
        assert solver._latest_snapshot_handle is None
    else:
        assert outcome.committed
        assert solver.adapter.updated.tolist() == [[-.5]]
    event_key = outcome.metadata["evaluation_disposition"]["event_snapshot_key"]
    event = solver.read_snapshot(event_key)[EVALUATION_EVENT_KEY]
    restored = OptimizationFeedbackBatch.from_dict(event["feedback_payload"])
    assert restored.violations.tolist() == [0., 0.]
    assert restored.raw_violations.tolist() == ([5., 5.] if provider else [0., 5.])


def test_nonfinite_raw_violations_are_rejected_even_with_zero_selection_view():
    raw = [float("nan"), float("inf"), 0., 1e-10, 5.]
    feedback = OptimizationFeedbackBatch.from_feedback(tuple(
        Feedback(objectives=[0.], info={"constraint_violation": 0.,
                 "raw_evaluation": {"objectives": [0.], "constraint_violation": value}})
        for value in raw))
    candidates = CandidateBatch.from_candidates([[0.]] * len(raw))
    disposition = FeasibleEvaluationAcceptance().select(candidates, feedback, {})
    assert disposition.accepted_indices == (2, 3)
    assert disposition.metadata["rejected_nonfinite_count"] == 2
