"""Template: permutation TSP using random keys + 2-opt mutation."""

import numpy as np

try:
    from nsgablack.core.base import BlackBoxProblem
    from nsgablack.core.composable_solver import ComposableSolver
    from nsgablack.core.adapters import VNSAdapter, VNSConfig
    from nsgablack.representation import RepresentationPipeline
    from nsgablack.representation.permutation import (
        PermutationInitializer,
        PermutationFixRepair,
        TwoOptMutation,
    )
    from nsgablack.utils.suites import attach_benchmark_harness, attach_module_report
except ModuleNotFoundError:  # pragma: no cover
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from nsgablack.core.base import BlackBoxProblem
    from nsgablack.core.composable_solver import ComposableSolver
    from nsgablack.core.adapters import VNSAdapter, VNSConfig
    from nsgablack.representation import RepresentationPipeline
    from nsgablack.representation.permutation import (
        PermutationInitializer,
        PermutationFixRepair,
        TwoOptMutation,
    )
    from nsgablack.utils.suites import attach_benchmark_harness, attach_module_report


class TSPProblem(BlackBoxProblem):
    def __init__(self, coords: np.ndarray):
        super().__init__(
            name="TSP",
            dimension=len(coords),
            bounds={f"x{i}": (0, len(coords) - 1) for i in range(len(coords))},
        )
        self.coords = np.asarray(coords, dtype=float)
        self.distance_matrix = self._build_distance(self.coords)

    def _build_distance(self, coords: np.ndarray) -> np.ndarray:
        n = len(coords)
        dist = np.zeros((n, n), dtype=float)
        for i in range(n):
            for j in range(n):
                dist[i, j] = float(np.linalg.norm(coords[i] - coords[j]))
        return dist

    def evaluate(self, x):
        perm = np.asarray(x, dtype=int)
        total = 0.0
        for i in range(len(perm)):
            j = (i + 1) % len(perm)
            total += self.distance_matrix[perm[i], perm[j]]
        return float(total)


def build_solver():
    rng = np.random.default_rng(123)
    coords = rng.uniform(0.0, 1.0, size=(20, 2))
    problem = TSPProblem(coords)

    pipeline = RepresentationPipeline(
        initializer=PermutationInitializer(),
        mutator=TwoOptMutation(max_iters=1),
        repair=PermutationFixRepair(),
    )

    adapter = VNSAdapter(VNSConfig(batch_size=6, k_max=4, base_sigma=0.2, scale=1.5))

    solver = ComposableSolver(problem=problem, adapter=adapter, representation_pipeline=pipeline)
    solver.max_steps = 80

    attach_benchmark_harness(solver, output_dir="runs", run_id="template_tsp", overwrite=True, log_every=1)
    attach_module_report(solver, output_dir="runs", run_id="template_tsp", write_bias_markdown=True)
    return solver


if __name__ == "__main__":
    solver = build_solver()
    result = solver.run()
    print("status:", result["status"], "steps:", result["steps"])
    print("best:", solver.best_objective)
