"""Sequence graph demo: capture component interaction order (values ignored)."""

from __future__ import annotations

import argparse
from pathlib import Path
import numpy as np

try:
    from nsgablack.core.base import BlackBoxProblem
    from nsgablack.core.composable_solver import ComposableSolver
    from nsgablack.core.adapters import SimulatedAnnealingAdapter, SAConfig
    from nsgablack.representation import RepresentationPipeline
    from nsgablack.representation.continuous import UniformInitializer, ContextGaussianMutation, ClipRepair
    from nsgablack.plugins import SequenceGraphPlugin, SequenceGraphConfig
except ModuleNotFoundError:  # pragma: no cover
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from nsgablack.core.base import BlackBoxProblem
    from nsgablack.core.composable_solver import ComposableSolver
    from nsgablack.core.adapters import SimulatedAnnealingAdapter, SAConfig
    from nsgablack.representation import RepresentationPipeline
    from nsgablack.representation.continuous import UniformInitializer, ContextGaussianMutation, ClipRepair
    from nsgablack.plugins import SequenceGraphPlugin, SequenceGraphConfig


class Sphere(BlackBoxProblem):
    def __init__(self, dimension: int = 6, low: float = -5.0, high: float = 5.0):
        super().__init__(name="Sphere", dimension=dimension, bounds={f"x{i}": (low, high) for i in range(dimension)})
        self.low = float(low)
        self.high = float(high)

    def evaluate(self, x):
        arr = np.asarray(x, dtype=float)
        return float(np.sum(arr * arr))


def build_solver(steps: int = 8, run_id: str = "sequence_graph_demo"):
    problem = Sphere()
    pipeline = RepresentationPipeline(
        initializer=UniformInitializer(low=problem.low, high=problem.high),
        mutator=ContextGaussianMutation(base_sigma=0.4, low=problem.low, high=problem.high),
        repair=ClipRepair(low=problem.low, high=problem.high),
    )
    adapter = SimulatedAnnealingAdapter(SAConfig(batch_size=6, initial_temperature=6.0, cooling_rate=0.96))
    solver = ComposableSolver(problem=problem, adapter=adapter, representation_pipeline=pipeline)
    solver.set_max_steps(int(steps))
    solver.add_plugin(
        SequenceGraphPlugin(
            config=SequenceGraphConfig(output_dir="runs", run_id=run_id),
        )
    )
    return solver


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--steps", type=int, default=8)
    parser.add_argument("--run-id", type=str, default="sequence_graph_demo")
    args = parser.parse_args()

    solver = build_solver(steps=args.steps, run_id=args.run_id)
    result = solver.run()
    graph_path = Path("runs") / f"{args.run_id}.sequence_graph.json"
    print("status:", result.get("status"), "steps:", result.get("steps"), "best:", float(solver.best_objective))
    print("sequence_graph:", graph_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
