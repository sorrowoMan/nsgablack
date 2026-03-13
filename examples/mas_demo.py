"""MAS (model-and-search) demo."""

import numpy as np

try:
    from nsgablack.core.base import BlackBoxProblem
    from nsgablack.core.composable_solver import ComposableSolver
    from nsgablack.adapters import MASAdapter, MASConfig
    from nsgablack.representation import RepresentationPipeline
    from nsgablack.representation.continuous import UniformInitializer, ContextGaussianMutation, ClipRepair
    from nsgablack.utils.wiring import attach_benchmark_harness
    from nsgablack.plugins import MASModelPlugin
except ModuleNotFoundError:  # pragma: no cover
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from nsgablack.core.base import BlackBoxProblem
    from nsgablack.core.composable_solver import ComposableSolver
    from nsgablack.adapters import MASAdapter, MASConfig
    from nsgablack.representation import RepresentationPipeline
    from nsgablack.representation.continuous import UniformInitializer, ContextGaussianMutation, ClipRepair
    from nsgablack.utils.wiring import attach_benchmark_harness
    from nsgablack.plugins import MASModelPlugin


class SphereProblem(BlackBoxProblem):
    def __init__(self, dimension=10, low=-5.0, high=5.0):
        super().__init__(
            name="SphereMAS",
            dimension=dimension,
            bounds={f"x{i}": (low, high) for i in range(dimension)},
        )
        self.low = low
        self.high = high

    def evaluate(self, x):
        x = np.asarray(x, dtype=float)
        return float(np.sum(x ** 2))


def build_solver():
    problem = SphereProblem()

    pipeline = RepresentationPipeline(
        initializer=UniformInitializer(low=problem.low, high=problem.high),
        mutator=ContextGaussianMutation(base_sigma=0.3, low=problem.low, high=problem.high),
        repair=ClipRepair(low=problem.low, high=problem.high),
    )

    adapter = MASAdapter(MASConfig(batch_size=16, exploration_ratio=0.5))

    solver = ComposableSolver(
        problem=problem,
        adapter=adapter,
        representation_pipeline=pipeline,
    )
    solver.set_max_steps(40)

    solver.add_plugin(MASModelPlugin())

    attach_benchmark_harness(
        solver,
        output_dir="runs",
        run_id="mas_demo",
        overwrite=True,
        log_every=1,
    )

    return solver


if __name__ == "__main__":
    solver = build_solver()
    result = solver.run()
    print("status:", result.get("status"))
    print("best:", solver.best_objective)

