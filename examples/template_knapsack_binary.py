"""Template: binary knapsack (capacity constraint via pipeline repair)."""

import numpy as np

try:
    from nsgablack.core.base import BlackBoxProblem
    from nsgablack.core.composable_solver import ComposableSolver
    from nsgablack.core.adapters import SimulatedAnnealingAdapter, SAConfig
    from nsgablack.representation import RepresentationPipeline
    from nsgablack.representation.binary import BinaryInitializer, BitFlipMutation, BinaryCapacityRepair
    from nsgablack.utils.suites import attach_benchmark_harness, attach_module_report
except ModuleNotFoundError:  # pragma: no cover
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from nsgablack.core.base import BlackBoxProblem
    from nsgablack.core.composable_solver import ComposableSolver
    from nsgablack.core.adapters import SimulatedAnnealingAdapter, SAConfig
    from nsgablack.representation import RepresentationPipeline
    from nsgablack.representation.binary import BinaryInitializer, BitFlipMutation, BinaryCapacityRepair
    from nsgablack.utils.suites import attach_benchmark_harness, attach_module_report


class KnapsackProblem(BlackBoxProblem):
    def __init__(self, values, weights, capacity):
        super().__init__(
            name="BinaryKnapsack",
            dimension=len(values),
            bounds={f"x{i}": (0, 1) for i in range(len(values))},
        )
        self.values = np.asarray(values, dtype=float)
        self.weights = np.asarray(weights, dtype=float)
        self.capacity = float(capacity)

    def evaluate(self, x):
        x = np.asarray(x, dtype=int)
        total_weight = float(np.dot(x, self.weights))
        if total_weight > self.capacity:
            # this should be rare if repair is enabled
            return float(1e6 + total_weight)
        total_value = float(np.dot(x, self.values))
        return -total_value  # maximize value -> minimize negative


def build_solver():
    rng = np.random.default_rng(42)
    n_items = 40
    values = rng.uniform(5, 20, size=n_items)
    weights = rng.uniform(1, 10, size=n_items)
    capacity = float(np.sum(weights) * 0.3)

    problem = KnapsackProblem(values, weights, capacity)

    pipeline = RepresentationPipeline(
        initializer=BinaryInitializer(probability=0.4),
        mutator=BitFlipMutation(rate=0.05),
        repair=BinaryCapacityRepair(capacity=int(capacity)),
    )

    adapter = SimulatedAnnealingAdapter(SAConfig(batch_size=8, initial_temperature=6.0, cooling_rate=0.98))
    solver = ComposableSolver(problem=problem, adapter=adapter, representation_pipeline=pipeline)
    solver.max_steps = 80

    attach_benchmark_harness(solver, output_dir="runs", run_id="template_knapsack", overwrite=True, log_every=1)
    attach_module_report(solver, output_dir="runs", run_id="template_knapsack", write_bias_markdown=True)
    return solver


if __name__ == "__main__":
    solver = build_solver()
    result = solver.run()
    print("status:", result["status"], "steps:", result["steps"])
    print("best:", solver.best_objective)
