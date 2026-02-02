"""A* adapter demo on a simple 2D grid."""

import numpy as np

try:
    from nsgablack.core.base import BlackBoxProblem
    from nsgablack.core.composable_solver import ComposableSolver
    from nsgablack.core.adapters import AStarAdapter, AStarConfig
    from nsgablack.representation import RepresentationPipeline
    from nsgablack.representation.continuous import UniformInitializer, ClipRepair
    from nsgablack.utils.suites import attach_benchmark_harness, attach_module_report
except ModuleNotFoundError:  # pragma: no cover
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from nsgablack.core.base import BlackBoxProblem
    from nsgablack.core.composable_solver import ComposableSolver
    from nsgablack.core.adapters import AStarAdapter, AStarConfig
    from nsgablack.representation import RepresentationPipeline
    from nsgablack.representation.continuous import UniformInitializer, ClipRepair
    from nsgablack.utils.suites import attach_benchmark_harness, attach_module_report


class GridGoal(BlackBoxProblem):
    def __init__(self, goal=(8.0, 8.0), low=0.0, high=10.0):
        super().__init__(name="GridGoal", dimension=2, bounds={"x": (low, high), "y": (low, high)})
        self.goal = np.asarray(goal, dtype=float)
        self.low = low
        self.high = high

    def evaluate(self, x):
        x = np.asarray(x, dtype=float)
        return float(np.linalg.norm(x - self.goal))


def build_solver():
    problem = GridGoal()

    pipeline = RepresentationPipeline(
        initializer=UniformInitializer(low=problem.low, high=problem.high),
        repair=ClipRepair(low=problem.low, high=problem.high),
    )

    def neighbors(state, _context):
        x, y = state
        steps = [(1, 0), (-1, 0), (0, 1), (0, -1)]
        for dx, dy in steps:
            yield np.array([x + dx, y + dy], dtype=float)

    def heuristic(state, _context):
        return float(np.linalg.norm(np.asarray(state, dtype=float) - problem.goal))

    def goal_test(state, _context):
        return float(np.linalg.norm(np.asarray(state, dtype=float) - problem.goal)) < 1e-6

    adapter = AStarAdapter(
        neighbors=neighbors,
        heuristic=heuristic,
        goal_test=goal_test,
        start_state=np.array([0.0, 0.0], dtype=float),
        config=AStarConfig(max_expand_per_step=5, max_candidates_per_step=64, path_cost_mode="edge"),
    )

    solver = ComposableSolver(problem=problem, adapter=adapter, representation_pipeline=pipeline)
    solver.max_steps = 30

    attach_benchmark_harness(solver, output_dir="runs", run_id="astar_demo", overwrite=True, log_every=1)
    attach_module_report(solver, output_dir="runs", run_id="astar_demo", write_bias_markdown=True)
    return solver


if __name__ == "__main__":
    solver = build_solver()
    result = solver.run()
    print("status:", result["status"], "steps:", result["steps"])
    print("best:", solver.best_objective)
