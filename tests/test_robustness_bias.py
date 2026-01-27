import numpy as np


def test_robustness_bias_penalizes_high_mc_std():
    from nsgablack.core.base import BlackBoxProblem
    from nsgablack.core.composable_solver import ComposableSolver
    from nsgablack.core.adapters import AlgorithmAdapter
    from nsgablack.bias import BiasModule, RobustnessBias
    from nsgablack.utils.plugins import MonteCarloEvaluationPlugin, MonteCarloEvaluationConfig

    class HeteroscedasticNoisySphere(BlackBoxProblem):
        def __init__(self, dim=2):
            super().__init__(
                name="hetero_noisy_sphere",
                dimension=dim,
                bounds={f"x{i}": (-2.0, 2.0) for i in range(dim)},
            )

        def evaluate(self, x):
            x = np.asarray(x, dtype=float)
            base = float(np.sum(x * x))
            # Noise grows with |x0| -> higher mc_std for candidates with larger |x0|
            sigma = 0.05 + 0.5 * float(abs(x[0]))
            noise = np.random.normal(0.0, sigma)
            return base + noise

    class TwoCandidatesOnce(AlgorithmAdapter):
        def __init__(self):
            super().__init__(name="two_candidates")

        def propose(self, solver, context):
            # low-noise vs high-noise
            return [np.array([0.0, 0.0], dtype=float), np.array([1.5, 0.0], dtype=float)]

    problem = HeteroscedasticNoisySphere()
    bias = BiasModule()
    bias.add(RobustnessBias(weight=0.5, aggregate="mean"))

    solver = ComposableSolver(problem=problem, adapter=TwoCandidatesOnce(), bias_module=bias)
    solver.max_steps = 1
    solver.add_plugin(
        MonteCarloEvaluationPlugin(
            config=MonteCarloEvaluationConfig(mc_samples=64, reduce="mean", random_seed=0)
        )
    )
    solver.run()

    # Candidate[1] has larger |x0| -> larger noise sigma -> should get larger robustness penalty
    assert solver.objectives[1, 0] > solver.objectives[0, 0]


def test_robustness_bias_is_noop_without_mc_stats():
    import warnings

    from nsgablack.core.base import BlackBoxProblem
    from nsgablack.bias import RobustnessBias
    from nsgablack.bias.core.base import OptimizationContext

    class DeterministicSphere(BlackBoxProblem):
        def __init__(self, dim=2):
            super().__init__(name="sphere", dimension=dim, bounds={f"x{i}": (-1.0, 1.0) for i in range(dim)})

        def evaluate(self, x):
            x = np.asarray(x, dtype=float)
            return float(np.sum(x * x))

    bias = RobustnessBias(weight=1.0)
    ctx = OptimizationContext(generation=0, individual=np.zeros(2), population=[], metrics={})
    with warnings.catch_warnings(record=True) as rec:
        warnings.simplefilter("always")
        assert bias.compute(np.zeros(2), ctx) == 0.0
        # first time should warn
        assert any("mc_std" in str(w.message) for w in rec)

    # second time should be silent (per-instance warn-once)
    with warnings.catch_warnings(record=True) as rec:
        warnings.simplefilter("always")
        assert bias.compute(np.zeros(2), ctx) == 0.0
        assert len(rec) == 0


def test_suite_attach_monte_carlo_robustness_runs():
    from nsgablack.core.base import BlackBoxProblem
    from nsgablack.core.composable_solver import ComposableSolver
    from nsgablack.core.adapters import AlgorithmAdapter
    from nsgablack.utils.suites import attach_monte_carlo_robustness

    class NoisySphere(BlackBoxProblem):
        def __init__(self, dim=2):
            super().__init__(name="noisy", dimension=dim, bounds={f"x{i}": (-1.0, 1.0) for i in range(dim)})

        def evaluate(self, x):
            x = np.asarray(x, dtype=float)
            noise = np.random.normal(0.0, 0.1)
            return float(np.sum(x * x) + noise)

    class Fixed(AlgorithmAdapter):
        def __init__(self):
            super().__init__(name="fixed")

        def propose(self, solver, context):
            return [np.zeros(solver.dimension) for _ in range(4)]

    solver = ComposableSolver(problem=NoisySphere(), adapter=Fixed())
    solver.max_steps = 1
    attach_monte_carlo_robustness(solver, mc_samples=8, robustness_weight=0.2, random_seed=0)
    solver.run()
    assert solver.objectives is not None
