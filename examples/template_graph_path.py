"""Template: graph path-like selection with graph repairs."""

import numpy as np

try:
    from nsgablack.core.base import BlackBoxProblem
    from nsgablack.core.composable_solver import ComposableSolver
    from nsgablack.adapters import SimulatedAnnealingAdapter, SAConfig
    from nsgablack.representation import RepresentationPipeline
    from nsgablack.representation.graph import GraphEdgeInitializer, GraphEdgeMutation, GraphConnectivityRepair, GraphDegreeRepair
    from nsgablack.utils.suites import attach_benchmark_harness, attach_module_report
except ModuleNotFoundError:  # pragma: no cover
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from nsgablack.core.base import BlackBoxProblem
    from nsgablack.core.composable_solver import ComposableSolver
    from nsgablack.adapters import SimulatedAnnealingAdapter, SAConfig
    from nsgablack.representation import RepresentationPipeline
    from nsgablack.representation.graph import GraphEdgeInitializer, GraphEdgeMutation, GraphConnectivityRepair, GraphDegreeRepair
    from nsgablack.utils.suites import attach_benchmark_harness, attach_module_report


class GraphRepairChain:
    context_requires = ("num_nodes",)
    context_provides = ()
    context_mutates = ()
    context_cache = ()
    context_notes = ("Normalizes num_nodes in context and delegates to graph repair chain.",)

    def __init__(self, num_nodes: int):
        self.num_nodes = int(num_nodes)
        self.connect = GraphConnectivityRepair()
        self.degree = GraphDegreeRepair(min_degree=1, max_degree=2)

    def repair(self, x, context=None):
        ctx = dict(context or {})
        ctx.setdefault("num_nodes", self.num_nodes)
        x = self.connect.repair(x, ctx)
        x = self.degree.repair(x, ctx)
        return x


class GraphPathProblem(BlackBoxProblem):
    """Select edges to form a sparse connected graph (path-like)."""

    def __init__(self, num_nodes=12):
        self.num_nodes = int(num_nodes)
        edge_count = self.num_nodes * (self.num_nodes - 1) // 2
        super().__init__(
            name="GraphPath",
            dimension=edge_count,
            bounds={f"e{i}": (0, 1) for i in range(edge_count)},
        )
        rng = np.random.default_rng(0)
        self.edge_weights = rng.uniform(1.0, 10.0, size=edge_count)

    def evaluate(self, x):
        x = np.asarray(x, dtype=int)
        total_cost = float(np.dot(x, self.edge_weights))
        # small penalty for too many edges (encourage path-like sparsity)
        edge_count = int(np.sum(x))
        penalty = max(0, edge_count - (self.num_nodes - 1)) * 2.0
        return total_cost + penalty


def build_solver():
    problem = GraphPathProblem(num_nodes=12)

    pipeline = RepresentationPipeline(
        initializer=GraphEdgeInitializer(num_nodes=problem.num_nodes, density=0.2),
        mutator=GraphEdgeMutation(rate=0.03),
        repair=GraphRepairChain(problem.num_nodes),
    )

    adapter = SimulatedAnnealingAdapter(SAConfig(batch_size=8, initial_temperature=6.0, cooling_rate=0.98))
    solver = ComposableSolver(problem=problem, adapter=adapter, representation_pipeline=pipeline)
    solver.set_max_steps(80)

    attach_benchmark_harness(solver, output_dir="runs", run_id="template_graph_path", overwrite=True, log_every=1)
    attach_module_report(solver, output_dir="runs", run_id="template_graph_path", write_bias_markdown=True)
    return solver


if __name__ == "__main__":
    solver = build_solver()
    result = solver.run()
    print("status:", result["status"], "steps:", result["steps"])
    print("best:", solver.best_objective)
