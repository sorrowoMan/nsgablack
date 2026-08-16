import numpy as np


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


