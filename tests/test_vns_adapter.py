import numpy as np


def test_vns_adapter_improves_sphere():
    from nsgablack.core.base import BlackBoxProblem
    from nsgablack.core.composable_solver import ComposableSolver
    from nsgablack.adapters import VNSAdapter, VNSConfig
    from nsgablack.representation import RepresentationPipeline
    from nsgablack.representation.continuous import UniformInitializer, ContextGaussianMutation, ClipRepair

    class Sphere(BlackBoxProblem):
        def __init__(self, dim=5, low=-5.0, high=5.0):
            super().__init__(name="sphere", dimension=dim, bounds={f"x{i}": (low, high) for i in range(dim)})
            self.low, self.high = low, high

        def evaluate(self, x):
            x = np.asarray(x, dtype=float)
            return float(np.sum(x * x))

    problem = Sphere()
    pipeline = RepresentationPipeline(
        initializer=UniformInitializer(low=problem.low, high=problem.high),
        mutator=ContextGaussianMutation(base_sigma=0.2, sigma_key="mutation_sigma", low=problem.low, high=problem.high),
        repair=ClipRepair(low=problem.low, high=problem.high),
    )

    solver = ComposableSolver(
        problem=problem,
        adapter=VNSAdapter(VNSConfig(batch_size=30, k_max=4, base_sigma=0.2, scale=1.5)),
        representation_pipeline=pipeline,
    )
    solver.max_steps = 25
    solver.run()

    assert solver.best_objective is not None
    assert solver.best_objective < 10.0
