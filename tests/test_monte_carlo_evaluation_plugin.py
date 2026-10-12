import numpy as np
import pytest


@pytest.mark.parametrize("batch", [False, True])
def test_monte_carlo_statistics_reach_bias_once_and_preserve_measurement(batch):
    from nsgablack.core.base import BlackBoxProblem
    from nsgablack.core.composable_solver import ComposableSolver
    from nsgablack.bias import BiasModule, RobustnessBias
    from nsgablack.plugins import MonteCarloEvaluationProviderPlugin, MonteCarloEvaluationConfig
    from nsgablack.core.evaluation_feedback import OptimizationFeedbackBatch

    class AlternatingProblem(BlackBoxProblem):
        def __init__(self):
            super().__init__(name="alternating", dimension=1, bounds={"x0": (-1, 1)})
            self.calls = 0
        def evaluate(self, candidate):
            self.calls += 1
            return float((-1) ** self.calls)

    class CountedBias(RobustnessBias):
        calls = 0
        def compute(self, candidate, context):
            self.calls += 1
            assert np.allclose(context.metrics["mc_std"], 1.0)
            return super().compute(candidate, context)

    preference = CountedBias(weight=1.0)
    module = BiasModule()
    module.add(preference)
    solver = ComposableSolver(AlternatingProblem(), bias_module=module)
    solver.add_plugin(MonteCarloEvaluationProviderPlugin(
        config=MonteCarloEvaluationConfig(mc_samples=4)))
    if batch:
        objectives, violations = solver.evaluate_population(np.array([[0.0], [0.0]]))
        feedback = solver.get_last_feedback_batch()
    else:
        objectives, violations = solver.evaluate_individual(np.array([0.0]))
        feedback = OptimizationFeedbackBatch.from_feedback((solver._last_individual_feedback,))
    assert preference.calls == (2 if batch else 1)
    assert solver.problem.calls == (8 if batch else 4)
    assert np.allclose(objectives, 1.0)
    assert np.allclose(violations, 0.0)
    recovered = OptimizationFeedbackBatch.from_dict(feedback.as_dict())
    assert np.allclose(recovered.raw_objectives, 0.0)
    assert np.allclose(recovered.items[0].metrics["mc_std"], 1.0)


def test_monte_carlo_evaluation_plugin_averages_noise():
    from nsgablack.core.base import BlackBoxProblem
    from nsgablack.core.composable_solver import ComposableSolver
    from nsgablack.adapters import AlgorithmAdapter
    from nsgablack.plugins import MonteCarloEvaluationProviderPlugin, MonteCarloEvaluationConfig

    class NoisySphere(BlackBoxProblem):
        def __init__(self, dim=3):
            super().__init__(name="noisy_sphere", dimension=dim, bounds={f"x{i}": (-1.0, 1.0) for i in range(dim)})

        def evaluate(self, candidate):
            candidate = np.asarray(candidate, dtype=float)
            noise = np.random.normal(0.0, 0.3)
            return float(np.sum(candidate * candidate) + noise)

    class FixedCandidate(AlgorithmAdapter):
        def __init__(self):
            super().__init__(name="fixed")

        def propose(self, control, context):
            return [np.zeros(control.dimension) for _ in range(8)]

        def update(self, control, candidates, feedback, context):
            _ = (control, candidates, feedback, context)

    problem = NoisySphere()
    control = ComposableSolver(problem=problem, adapter=FixedCandidate())
    control.max_steps = 1
    control.register_evaluation_provider(
        MonteCarloEvaluationProviderPlugin(
            config=MonteCarloEvaluationConfig(mc_samples=40, reduce="mean", random_seed=0)
        ).create_provider()
    )
    control.run()

    # Expect mean close to 0 for x=0 (noise averaged out)
    assert control.last_step_summary["best_objective"] < 0.5


