"""Single-trajectory adaptive search demo."""

from __future__ import annotations

import numpy as np

try:
    from nsgablack.core.base import BlackBoxProblem
    from nsgablack.core.composable_solver import ComposableSolver
    from nsgablack.adapters import SingleTrajectoryAdaptiveAdapter, SingleTrajectoryAdaptiveConfig
    from nsgablack.representation import RepresentationPipeline
    from nsgablack.representation.continuous import ClipRepair, ContextGaussianMutation, UniformInitializer
except ModuleNotFoundError:  # pragma: no cover
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from nsgablack.core.base import BlackBoxProblem
    from nsgablack.core.composable_solver import ComposableSolver
    from nsgablack.adapters import SingleTrajectoryAdaptiveAdapter, SingleTrajectoryAdaptiveConfig
    from nsgablack.representation import RepresentationPipeline
    from nsgablack.representation.continuous import ClipRepair, ContextGaussianMutation, UniformInitializer


class SphereProblem(BlackBoxProblem):
    def __init__(self, dimension: int = 12, low: float = -5.0, high: float = 5.0):
        super().__init__(
            name="SingleTrajectorySphere",
            dimension=dimension,
            bounds={f"x{i}": (low, high) for i in range(dimension)},
        )

    def evaluate(self, x):
        x = np.asarray(x, dtype=float)
        return float(np.sum(x**2))


def build_solver():
    np.random.seed(11)

    problem = SphereProblem(dimension=10, low=-5.0, high=5.0)
    pipeline = RepresentationPipeline(
        initializer=UniformInitializer(low=-5.0, high=5.0),
        mutator=ContextGaussianMutation(base_sigma=0.35, low=-5.0, high=5.0),
        repair=ClipRepair(low=-5.0, high=5.0),
    )

    solver = ComposableSolver(problem=problem, representation_pipeline=pipeline)
    solver.set_max_steps(40)

    solver.set_adapter(
        SingleTrajectoryAdaptiveAdapter(
            config=SingleTrajectoryAdaptiveConfig(
            batch_size=10,
            initial_sigma=0.45,
            min_sigma=0.03,
            max_sigma=1.8,
            target_success_rate=0.25,
            restart_patience=15,
            ),
        )
    )
    return solver


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--ui", action="store_true", help="Launch Run Inspector UI before running.")
    args = parser.parse_args()

    from nsgablack.utils.viz import launch_from_builder, maybe_launch_ui

    entry_label = "examples/single_trajectory_adaptive_demo.py:build_solver"
    if args.ui:
        launch_from_builder(build_solver, entry_label=entry_label)
    elif maybe_launch_ui(build_solver, entry_label=entry_label):
        pass
    else:
        solver = build_solver()
        result = solver.run()
        print("status:", result.get("status"), "steps:", result.get("steps"))
        print("best_objective:", getattr(solver, "best_objective", None))
        print("sta_sigma:", getattr(solver, "sta_sigma", None))

