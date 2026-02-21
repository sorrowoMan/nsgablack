"""Async event-driven optimization demo.

Shows how to combine:
- AsyncEventDrivenAdapter (event queue orchestration)
- AsyncEventHubPlugin (event commit/replay boundary)
- ParetoArchivePlugin (shared frontier state)
"""

from __future__ import annotations

import numpy as np

try:
    from nsgablack.core.base import BlackBoxProblem
    from nsgablack.core.composable_solver import ComposableSolver
    from nsgablack.core.adapters import (
        AsyncEventDrivenConfig,
        EventStrategySpec,
        SAConfig,
        SimulatedAnnealingAdapter,
        VNSAdapter,
        VNSConfig,
    )
    from nsgablack.representation import RepresentationPipeline
    from nsgablack.representation.continuous import ClipRepair, ContextGaussianMutation, UniformInitializer
    from nsgablack.utils.suites import attach_async_event_driven
except ModuleNotFoundError:  # pragma: no cover
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from nsgablack.core.base import BlackBoxProblem
    from nsgablack.core.composable_solver import ComposableSolver
    from nsgablack.core.adapters import (
        AsyncEventDrivenConfig,
        EventStrategySpec,
        SAConfig,
        SimulatedAnnealingAdapter,
        VNSAdapter,
        VNSConfig,
    )
    from nsgablack.representation import RepresentationPipeline
    from nsgablack.representation.continuous import ClipRepair, ContextGaussianMutation, UniformInitializer
    from nsgablack.utils.suites import attach_async_event_driven


class SphereProblem(BlackBoxProblem):
    def __init__(self, dimension: int = 10, low: float = -5.0, high: float = 5.0) -> None:
        super().__init__(
            name="AsyncEventSphere",
            dimension=dimension,
            bounds={f"x{i}": (low, high) for i in range(dimension)},
        )

    def evaluate(self, x):
        x = np.asarray(x, dtype=float)
        return float(np.sum(x ** 2))


def build_solver():
    np.random.seed(7)
    problem = SphereProblem(dimension=8, low=-5.0, high=5.0)

    pipeline = RepresentationPipeline(
        initializer=UniformInitializer(low=-5.0, high=5.0),
        mutator=ContextGaussianMutation(base_sigma=0.35, low=-5.0, high=5.0),
        repair=ClipRepair(low=-5.0, high=5.0),
    )

    solver = ComposableSolver(problem=problem, representation_pipeline=pipeline)
    solver.set_max_steps(30)

    strategies = [
        EventStrategySpec(
            adapter=SimulatedAnnealingAdapter(SAConfig(batch_size=2, initial_temperature=8.0, cooling_rate=0.97)),
            name="sa",
            weight=0.8,
        ),
        EventStrategySpec(
            adapter=VNSAdapter(VNSConfig(batch_size=4, k_max=4, base_sigma=0.2, scale=1.5)),
            name="vns",
            weight=1.2,
        ),
    ]
    config = AsyncEventDrivenConfig(
        total_batch_size=24,
        target_queue_size=64,
        bootstrap_events_per_strategy=10,
        max_archive_size=300,
    )

    attach_async_event_driven(
        solver,
        strategies=strategies,
        config=config,
        attach_async_hub=True,
        attach_pareto_archive=True,
    )
    return solver


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--ui", action="store_true", help="Launch Run Inspector UI before running.")
    args = parser.parse_args()

    from nsgablack.utils.viz import launch_from_builder, maybe_launch_ui

    entry_label = "examples/async_event_driven_demo.py:build_solver"
    if args.ui:
        launch_from_builder(build_solver, entry_label=entry_label)
    elif maybe_launch_ui(build_solver, entry_label=entry_label):
        pass
    else:
        solver = build_solver()
        result = solver.run()
        print("status:", result.get("status"), "steps:", result.get("steps"))
        state = getattr(solver, "event_shared_state", {}) or {}
        print("event_queue:", state.get("queue_size"), "archive:", state.get("archive_size"))
        print("best_objective:", getattr(solver, "best_objective", None))

