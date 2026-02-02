"""Subspace trust-region demo (CUATRO_PLS-style)."""

import numpy as np

try:
    from nsgablack.core.base import BlackBoxProblem
    from nsgablack.core.composable_solver import ComposableSolver
    from nsgablack.core.adapters import TrustRegionSubspaceAdapter, TrustRegionSubspaceConfig
    from nsgablack.representation import RepresentationPipeline
    from nsgablack.representation.continuous import UniformInitializer, ContextGaussianMutation, ClipRepair
    from nsgablack.utils.suites import attach_benchmark_harness
    from nsgablack.utils.plugins import SubspaceBasisPlugin, SubspaceBasisConfig
except ModuleNotFoundError:  # pragma: no cover
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from nsgablack.core.base import BlackBoxProblem
    from nsgablack.core.composable_solver import ComposableSolver
    from nsgablack.core.adapters import TrustRegionSubspaceAdapter, TrustRegionSubspaceConfig
    from nsgablack.representation import RepresentationPipeline
    from nsgablack.representation.continuous import UniformInitializer, ContextGaussianMutation, ClipRepair
    from nsgablack.utils.suites import attach_benchmark_harness
    from nsgablack.utils.plugins import SubspaceBasisPlugin, SubspaceBasisConfig


class SphereProblem(BlackBoxProblem):
    def __init__(self, dimension=20, low=-5.0, high=5.0):
        super().__init__(
            name="SphereTRSubspace",
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

    adapter = TrustRegionSubspaceAdapter(
        TrustRegionSubspaceConfig(
            batch_size=16,
            initial_radius=1.0,
            subspace_dim=6,
            resample_every=5,
        )
    )

    solver = ComposableSolver(
        problem=problem,
        adapter=adapter,
        representation_pipeline=pipeline,
    )
    solver.max_steps = 40

    solver.add_plugin(
        SubspaceBasisPlugin(
            config=SubspaceBasisConfig(method="pca", subspace_dim=6, min_samples=16)
        )
    )

    attach_benchmark_harness(
        solver,
        output_dir="runs",
        run_id="trust_region_subspace_demo",
        overwrite=True,
        log_every=1,
    )

    return solver


if __name__ == "__main__":
    solver = build_solver()
    result = solver.run()
    print("status:", result.get("status"))
    print("best:", solver.best_objective)
