"""Template: simplified production scheduling (matrix + demand constraints)."""

import numpy as np

try:
    from nsgablack.core.base import BlackBoxProblem
    from nsgablack.core.composable_solver import ComposableSolver
    from nsgablack.adapters import SimulatedAnnealingAdapter, SAConfig
    from nsgablack.representation import RepresentationPipeline
    from nsgablack.representation.matrix import IntegerMatrixInitializer, IntegerMatrixMutation, MatrixRowColSumRepair
    from nsgablack.utils.suites import attach_benchmark_harness, attach_module_report
except ModuleNotFoundError:  # pragma: no cover
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from nsgablack.core.base import BlackBoxProblem
    from nsgablack.core.composable_solver import ComposableSolver
    from nsgablack.adapters import SimulatedAnnealingAdapter, SAConfig
    from nsgablack.representation import RepresentationPipeline
    from nsgablack.representation.matrix import IntegerMatrixInitializer, IntegerMatrixMutation, MatrixRowColSumRepair
    from nsgablack.utils.suites import attach_benchmark_harness, attach_module_report


class ProductionScheduleProblem(BlackBoxProblem):
    """Matrix schedule: machines x days, each day must meet demand."""

    def __init__(self, cost: np.ndarray, daily_demand: np.ndarray):
        m, d = cost.shape
        super().__init__(
            name="ProductionScheduleSimple",
            dimension=m * d,
            bounds={f"x{i}": (0, 1) for i in range(m * d)},
        )
        self.cost = np.asarray(cost, dtype=float)
        self.daily_demand = np.asarray(daily_demand, dtype=int)
        self.matrix_shape = (m, d)

    def evaluate(self, x):
        mat = np.asarray(x, dtype=float).reshape(self.matrix_shape)
        total_cost = float(np.sum(mat * self.cost))
        # penalize switching (production changes per machine)
        switch_penalty = float(np.sum(np.abs(np.diff(mat, axis=1))))
        return total_cost + 0.5 * switch_penalty


def build_solver():
    rng = np.random.default_rng(9)
    machines, days = 5, 10
    cost = rng.uniform(1.0, 5.0, size=(machines, days))
    daily_demand = np.ones(days, dtype=int) * 2

    problem = ProductionScheduleProblem(cost, daily_demand)

    pipeline = RepresentationPipeline(
        initializer=IntegerMatrixInitializer(rows=machines, cols=days, low=0, high=1),
        mutator=IntegerMatrixMutation(sigma=0.6, low=0, high=1),
        repair=MatrixRowColSumRepair(row_sums=None, col_sums=daily_demand, max_passes=6),
    )

    adapter = SimulatedAnnealingAdapter(SAConfig(batch_size=6, initial_temperature=6.0, cooling_rate=0.98))
    solver = ComposableSolver(problem=problem, adapter=adapter, representation_pipeline=pipeline)
    solver.set_max_steps(80)

    attach_benchmark_harness(solver, output_dir="runs", run_id="template_production_simple", overwrite=True, log_every=1)
    attach_module_report(solver, output_dir="runs", run_id="template_production_simple", write_bias_markdown=True)
    return solver


if __name__ == "__main__":
    solver = build_solver()
    result = solver.run()
    print("status:", result["status"], "steps:", result["steps"])
    print("best:", solver.best_objective)
