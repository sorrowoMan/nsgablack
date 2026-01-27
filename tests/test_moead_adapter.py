import numpy as np


def test_moead_adapter_runs_and_updates_archive():
    from nsgablack.core.base import BlackBoxProblem
    from nsgablack.core.composable_solver import ComposableSolver
    from nsgablack.core.adapters import MOEADAdapter, MOEADConfig
    from nsgablack.representation import RepresentationPipeline
    from nsgablack.representation.continuous import UniformInitializer, GaussianMutation, ClipRepair
    from nsgablack.utils.plugins import ParetoArchivePlugin

    class BiSphere(BlackBoxProblem):
        def __init__(self, dim=4, low=-3.0, high=3.0):
            super().__init__(
                name="bi_sphere",
                dimension=dim,
                bounds={f"x{i}": (low, high) for i in range(dim)},
                objectives=["f1", "f2"],
            )
            self.low, self.high = low, high

        def evaluate(self, x):
            x = np.asarray(x, dtype=float)
            f1 = float(np.sum(x * x))
            f2 = float(np.sum((x - 2.0) ** 2))
            return np.array([f1, f2], dtype=float)

    problem = BiSphere()
    pipeline = RepresentationPipeline(
        initializer=UniformInitializer(low=problem.low, high=problem.high),
        mutator=GaussianMutation(sigma=0.4, low=problem.low, high=problem.high),
        repair=ClipRepair(low=problem.low, high=problem.high),
    )

    adapter = MOEADAdapter(MOEADConfig(population_size=40, neighborhood_size=10, batch_size=20, nr=2))
    solver = ComposableSolver(problem=problem, adapter=adapter, representation_pipeline=pipeline)
    solver.add_plugin(ParetoArchivePlugin())
    solver.max_steps = 15
    solver.run()

    X, F, V = adapter.get_population()
    assert X.shape[0] == 40
    assert F.shape[1] == 2
    assert V.shape[0] == 40

    assert getattr(solver, "pareto_objectives", None) is not None
    assert np.asarray(solver.pareto_objectives).ndim == 2
    assert np.asarray(solver.pareto_objectives).shape[1] == 2
