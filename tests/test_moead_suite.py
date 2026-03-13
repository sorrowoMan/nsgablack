import numpy as np


def test_moead_adapter_direct_wiring_installs_archive():
    from nsgablack.core.base import BlackBoxProblem
    from nsgablack.core.composable_solver import ComposableSolver
    from nsgablack.adapters import MOEADAdapter, MOEADConfig
    from nsgablack.plugins import ParetoArchivePlugin
    from nsgablack.representation import RepresentationPipeline
    from nsgablack.representation.continuous import UniformInitializer, GaussianMutation, ClipRepair

    class BiSphere(BlackBoxProblem):
        def __init__(self, dim=3, low=-3.0, high=3.0):
            super().__init__(
                name="bi_sphere",
                dimension=dim,
                bounds={f"x{i}": (low, high) for i in range(dim)},
                objectives=["f1", "f2"],
            )
            self.low, self.high = low, high

        def evaluate(self, x):
            x = np.asarray(x, dtype=float)
            return np.array([np.sum(x * x), np.sum((x - 2.0) ** 2)], dtype=float)

    pipeline = RepresentationPipeline(
        initializer=UniformInitializer(low=-3.0, high=3.0),
        mutator=GaussianMutation(sigma=0.5, low=-3.0, high=3.0),
        repair=ClipRepair(low=-3.0, high=3.0),
    )
    solver = ComposableSolver(problem=BiSphere(), representation_pipeline=pipeline, adapter=None)
    solver.max_steps = 3
    solver.set_adapter(MOEADAdapter(MOEADConfig()))
    solver.add_plugin(ParetoArchivePlugin())
    solver.run()
    assert getattr(solver, "adapter", None) is not None
    assert getattr(solver, "pareto_objectives", None) is not None
