"""Trust-region DFO demo (local search)."""

import numpy as np

try:
    from nsgablack.core.base import BlackBoxProblem
    from nsgablack.core.composable_solver import ComposableSolver
    from nsgablack.adapters import TrustRegionDFOAdapter, TrustRegionDFOConfig
    from nsgablack.representation import RepresentationPipeline
    from nsgablack.representation.continuous import UniformInitializer, ContextGaussianMutation, ClipRepair
    from nsgablack.utils.suites import attach_benchmark_harness
except ModuleNotFoundError:  # pragma: no cover
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from nsgablack.core.base import BlackBoxProblem
    from nsgablack.core.composable_solver import ComposableSolver
    from nsgablack.adapters import TrustRegionDFOAdapter, TrustRegionDFOConfig
    from nsgablack.representation import RepresentationPipeline
    from nsgablack.representation.continuous import UniformInitializer, ContextGaussianMutation, ClipRepair
    from nsgablack.utils.suites import attach_benchmark_harness


class SphereProblem(BlackBoxProblem):
    def __init__(self, dimension=6, low=-5.0, high=5.0):
        super().__init__(
            name="SphereTRDFO",
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

    adapter = TrustRegionDFOAdapter(
        TrustRegionDFOConfig(
            batch_size=12,
            initial_radius=1.0,
            min_radius=1e-4,
            max_radius=3.0,
        )
    )

    solver = ComposableSolver(
        problem=problem,
        adapter=adapter,
        representation_pipeline=pipeline,
    )
    solver.set_max_steps(40)

    attach_benchmark_harness(
        solver,
        output_dir="runs",
        run_id="trust_region_dfo_demo",
        overwrite=True,
        log_every=1,
    )

    return solver


if __name__ == "__main__":
    solver = build_solver()
    result = solver.run()
    print("status:", result.get("status"))
    print("best:", solver.best_objective)
