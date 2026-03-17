"""Non-smooth trust-region demo."""

import numpy as np

try:
    from nsgablack.core.base import BlackBoxProblem
    from nsgablack.core.composable_solver import ComposableSolver
    from nsgablack.adapters import TrustRegionNonSmoothAdapter, TrustRegionNonSmoothConfig
    from nsgablack.representation import RepresentationPipeline
    from nsgablack.representation.continuous import UniformInitializer, ContextGaussianMutation, ClipRepair
    from nsgablack.utils.wiring import attach_benchmark_harness
except ModuleNotFoundError:  # pragma: no cover
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from nsgablack.core.base import BlackBoxProblem
    from nsgablack.core.composable_solver import ComposableSolver
    from nsgablack.adapters import TrustRegionNonSmoothAdapter, TrustRegionNonSmoothConfig
    from nsgablack.representation import RepresentationPipeline
    from nsgablack.representation.continuous import UniformInitializer, ContextGaussianMutation, ClipRepair
    from nsgablack.utils.wiring import attach_benchmark_harness


class AbsSphereProblem(BlackBoxProblem):
    def __init__(self, dimension=8, low=-5.0, high=5.0):
        super().__init__(
            name="AbsSphereTRNS",
            dimension=dimension,
            bounds={f"x{i}": (low, high) for i in range(dimension)},
        )
        self.low = low
        self.high = high

    def evaluate(self, x):
        x = np.asarray(x, dtype=float)
        return float(np.sum(np.abs(x)))


def build_solver():
    problem = AbsSphereProblem()

    pipeline = RepresentationPipeline(
        initializer=UniformInitializer(low=problem.low, high=problem.high),
        mutator=ContextGaussianMutation(base_sigma=0.3, low=problem.low, high=problem.high),
        repair=ClipRepair(low=problem.low, high=problem.high),
    )

    adapter = TrustRegionNonSmoothAdapter(
        TrustRegionNonSmoothConfig(
            batch_size=16,
            initial_radius=1.0,
            score_mode="l1",
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
        run_id="trust_region_nonsmooth_demo",
        overwrite=True,
        log_every=1,
    )

    return solver


if __name__ == "__main__":
    solver = build_solver()
    result = solver.run()
    print("status:", result.get("status"))
    print("best:", solver.best_objective)
