"""Template: assignment matrix (row/col sum constraints)."""

import numpy as np

try:
    from nsgablack.core.base import BlackBoxProblem
    from nsgablack.core.composable_solver import ComposableSolver
    from nsgablack.core.adapters import SimulatedAnnealingAdapter, SAConfig
    from nsgablack.representation import RepresentationPipeline
    from nsgablack.representation.matrix import IntegerMatrixInitializer, IntegerMatrixMutation, MatrixRowColSumRepair
    from nsgablack.utils.suites import attach_benchmark_harness, attach_module_report
except ModuleNotFoundError:  # pragma: no cover
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from nsgablack.core.base import BlackBoxProblem
    from nsgablack.core.composable_solver import ComposableSolver
    from nsgablack.core.adapters import SimulatedAnnealingAdapter, SAConfig
    from nsgablack.representation import RepresentationPipeline
    from nsgablack.representation.matrix import IntegerMatrixInitializer, IntegerMatrixMutation, MatrixRowColSumRepair
    from nsgablack.utils.suites import attach_benchmark_harness, attach_module_report


class AssignmentProblem(BlackBoxProblem):
    """Minimize assignment cost with row/col sums = 1 (binary-like matrix)."""

    def __init__(self, cost: np.ndarray):
        n = cost.shape[0]
        super().__init__(
            name="AssignmentMatrix",
            dimension=n * n,
            bounds={f"x{i}": (0, 1) for i in range(n * n)},
        )
        self.cost = np.asarray(cost, dtype=float)
        self.matrix_shape = (n, n)

    def evaluate(self, x):
        mat = np.asarray(x, dtype=float).reshape(self.matrix_shape)
        return float(np.sum(mat * self.cost))


def build_solver():
    rng = np.random.default_rng(7)
    n = 8
    cost = rng.uniform(1.0, 10.0, size=(n, n))
    problem = AssignmentProblem(cost)

    pipeline = RepresentationPipeline(
        initializer=IntegerMatrixInitializer(rows=n, cols=n, low=0, high=1),
        mutator=IntegerMatrixMutation(sigma=0.6, low=0, high=1),
        repair=MatrixRowColSumRepair(
            row_sums=np.ones(n, dtype=int),
            col_sums=np.ones(n, dtype=int),
            max_passes=8,
        ),
    )

    adapter = SimulatedAnnealingAdapter(SAConfig(batch_size=6, initial_temperature=6.0, cooling_rate=0.97))
    solver = ComposableSolver(problem=problem, adapter=adapter, representation_pipeline=pipeline)
    solver.set_max_steps(80)

    attach_benchmark_harness(solver, output_dir="runs", run_id="template_assignment", overwrite=True, log_every=1)
    attach_module_report(solver, output_dir="runs", run_id="template_assignment", write_bias_markdown=True)
    return solver


if __name__ == "__main__":
    solver = build_solver()
    result = solver.run()
    print("status:", result["status"], "steps:", result["steps"])
    print("best:", solver.best_objective)
