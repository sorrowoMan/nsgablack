import numpy as np


def test_surrogate_evaluation_plugin_reduces_true_evals_for_composable_solver():
    from nsgablack.core.base import BlackBoxProblem
    from nsgablack.core.composable_solver import ComposableSolver
    from nsgablack.adapters import AlgorithmAdapter
    from nsgablack.plugins import SurrogateEvaluationPlugin, SurrogateEvaluationConfig

    class ExpensiveSphere(BlackBoxProblem):
        def __init__(self, dim=5):
            super().__init__(name="expensive_sphere", dimension=dim, bounds={f"x{i}": (-5.0, 5.0) for i in range(dim)})

        def evaluate(self, x):
            x = np.asarray(x, dtype=float)
            return float(np.sum(x * x))

    class RandomBatchAdapter(AlgorithmAdapter):
        def __init__(self, n_candidates=30):
            super().__init__(name="random_batch")
            self.n_candidates = int(n_candidates)

        def propose(self, solver, context):
            lows = np.array([solver.var_bounds[f"x{i}"][0] for i in range(solver.dimension)], dtype=float)
            highs = np.array([solver.var_bounds[f"x{i}"][1] for i in range(solver.dimension)], dtype=float)
            return [np.random.uniform(lows, highs, size=solver.dimension) for _ in range(self.n_candidates)]

    problem = ExpensiveSphere(dim=6)
    solver = ComposableSolver(problem=problem, adapter=RandomBatchAdapter(n_candidates=30))
    solver.max_steps = 5

    cfg = SurrogateEvaluationConfig(
        min_train_samples=25,
        min_true_evals=5,
        topk_exploit=5,
        topk_explore=5,
        retrain_every_call=True,
        objective_aggregation="sum",
        random_seed=0,
    )
    plugin = SurrogateEvaluationPlugin(config=cfg, model_type="rf")
    solver.add_plugin(plugin)

    solver.run()

    total_candidates = 30 * 5
    assert plugin.stats["true_evals"] > 0
    assert plugin.stats["true_evals"] < total_candidates
    assert problem.evaluation_count == plugin.stats["true_evals"]

