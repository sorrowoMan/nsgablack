"""Minimal OpenTelemetry tracing demo for NSGABlack.

Run:
  python examples/otel_tracing_demo.py

Optional OTLP export:
  python examples/otel_tracing_demo.py --otlp-endpoint http://127.0.0.1:4318/v1/traces
"""

from __future__ import annotations

import argparse
import numpy as np

try:
    from nsgablack.core.base import BlackBoxProblem
    from nsgablack.core.composable_solver import ComposableSolver
    from nsgablack.adapters import SimulatedAnnealingAdapter, SAConfig
    from nsgablack.representation import RepresentationPipeline
    from nsgablack.representation.continuous import UniformInitializer, ContextGaussianMutation, ClipRepair
    from nsgablack.plugins import OpenTelemetryTracingPlugin, OpenTelemetryTracingConfig
except ModuleNotFoundError:  # pragma: no cover
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from nsgablack.core.base import BlackBoxProblem
    from nsgablack.core.composable_solver import ComposableSolver
    from nsgablack.adapters import SimulatedAnnealingAdapter, SAConfig
    from nsgablack.representation import RepresentationPipeline
    from nsgablack.representation.continuous import UniformInitializer, ContextGaussianMutation, ClipRepair
    from nsgablack.plugins import OpenTelemetryTracingPlugin, OpenTelemetryTracingConfig


class Sphere(BlackBoxProblem):
    def __init__(self, dimension: int = 6, low: float = -5.0, high: float = 5.0):
        super().__init__(name="Sphere", dimension=dimension, bounds={f"x{i}": (low, high) for i in range(dimension)})
        self.low = float(low)
        self.high = float(high)

    def evaluate(self, x):
        arr = np.asarray(x, dtype=float)
        return float(np.sum(arr * arr))


def build_solver(steps: int, console_export: bool, otlp_endpoint: str):
    problem = Sphere()
    pipeline = RepresentationPipeline(
        initializer=UniformInitializer(low=problem.low, high=problem.high),
        mutator=ContextGaussianMutation(base_sigma=0.35, low=problem.low, high=problem.high),
        repair=ClipRepair(low=problem.low, high=problem.high),
    )
    adapter = SimulatedAnnealingAdapter(SAConfig(batch_size=8, initial_temperature=5.0, cooling_rate=0.97))
    solver = ComposableSolver(problem=problem, adapter=adapter, representation_pipeline=pipeline)
    solver.set_max_steps(int(steps))

    solver.add_plugin(
        OpenTelemetryTracingPlugin(
            config=OpenTelemetryTracingConfig(
                service_name="nsgablack-otel-demo",
                service_version="0.1",
                console_export=bool(console_export),
                otlp_http_endpoint=str(otlp_endpoint or ""),
            )
        )
    )
    return solver


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--steps", type=int, default=20)
    parser.add_argument("--console-export", action="store_true", default=True)
    parser.add_argument("--no-console-export", action="store_true")
    parser.add_argument("--otlp-endpoint", type=str, default="")
    args = parser.parse_args()

    solver = build_solver(
        steps=args.steps,
        console_export=bool(args.console_export and not args.no_console_export),
        otlp_endpoint=args.otlp_endpoint,
    )
    result = solver.run()
    print("status:", result.get("status"), "steps:", result.get("steps"), "best:", float(solver.best_objective))
    artifacts = result.get("artifacts", {}) if isinstance(result, dict) else {}
    print("otel:", artifacts.get("otel_tracing", {}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
