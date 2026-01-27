import numpy as np


def test_monte_carlo_evaluation_plugin_averages_noise():
    from nsgablack.core.base import BlackBoxProblem
    from nsgablack.core.composable_solver import ComposableSolver
    from nsgablack.core.adapters import AlgorithmAdapter
    from nsgablack.utils.plugins import MonteCarloEvaluationPlugin, MonteCarloEvaluationConfig

    class NoisySphere(BlackBoxProblem):
        def __init__(self, dim=3):
            super().__init__(name="noisy_sphere", dimension=dim, bounds={f"x{i}": (-1.0, 1.0) for i in range(dim)})

        def evaluate(self, x):
            x = np.asarray(x, dtype=float)
            noise = np.random.normal(0.0, 0.3)
            return float(np.sum(x * x) + noise)

    class FixedCandidate(AlgorithmAdapter):
        def __init__(self):
            super().__init__(name="fixed")

        def propose(self, solver, context):
            return [np.zeros(solver.dimension) for _ in range(8)]

    problem = NoisySphere()
    solver = ComposableSolver(problem=problem, adapter=FixedCandidate())
    solver.max_steps = 1
    solver.add_plugin(MonteCarloEvaluationPlugin(config=MonteCarloEvaluationConfig(mc_samples=40, reduce="mean", random_seed=0)))
    solver.run()

    # Expect mean close to 0 for x=0 (noise averaged out)
    assert solver.last_step_summary["best_objective"] < 0.5
