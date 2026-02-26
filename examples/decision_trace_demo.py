"""Decision trace demo: replay why decisions happened at each generation."""

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
    from nsgablack.plugins import DecisionTracePlugin, DecisionTraceConfig
    from nsgablack.plugins.base import Plugin
    from nsgablack.utils.runtime import DecisionReplayEngine, record_decision_event
except ModuleNotFoundError:  # pragma: no cover
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from nsgablack.core.base import BlackBoxProblem
    from nsgablack.core.composable_solver import ComposableSolver
    from nsgablack.core.adapters import SimulatedAnnealingAdapter, SAConfig
    from nsgablack.representation import RepresentationPipeline
    from nsgablack.representation.continuous import UniformInitializer, ContextGaussianMutation, ClipRepair
    from nsgablack.plugins import DecisionTracePlugin, DecisionTraceConfig
    from nsgablack.plugins.base import Plugin
    from nsgablack.utils.runtime import DecisionReplayEngine, record_decision_event


class Sphere(BlackBoxProblem):
    def __init__(self, dimension: int = 6, low: float = -5.0, high: float = 5.0):
        super().__init__(name="Sphere", dimension=dimension, bounds={f"x{i}": (low, high) for i in range(dimension)})
        self.low = float(low)
        self.high = float(high)

    def evaluate(self, x):
        arr = np.asarray(x, dtype=float)
        return float(np.sum(arr * arr))


class DecisionSignalPlugin(Plugin):
    """Emit semantic decision events to prove replay path."""

    context_requires = ("generation",)
    context_provides = ()
    context_mutates = ()
    context_cache = ()
    context_notes = ("Emit synthetic fallback/surrogate/inner_budget decisions for demo.",)

    def __init__(self):
        super().__init__(name="decision_signal")

    def on_generation_end(self, generation: int):
        solver = self.solver
        if solver is None:
            return None
        g = int(generation)
        if g == 3:
            record_decision_event(
                solver,
                event_type="fallback",
                component="plugin.surrogate_router",
                decision="fallback_to_truth",
                reason_code="surrogate_confidence_below_threshold",
                inputs={"confidence": 0.42},
                thresholds={"min_confidence": 0.7},
                evidence={"window": 16},
                outcome={"mode": "truth_eval"},
            )
        if g == 5:
            record_decision_event(
                solver,
                event_type="inner_budget",
                component="plugin.inner_solver",
                decision="expand_budget",
                reason_code="residual_not_decreasing",
                inputs={"residual": 0.18},
                thresholds={"target_residual": 0.05},
                evidence={"prev_budget": 40, "new_budget": 80},
                outcome={"expanded": True},
            )
        if g == 7:
            record_decision_event(
                solver,
                event_type="surrogate_trigger",
                component="plugin.surrogate_router",
                decision="enable_surrogate",
                reason_code="error_stable_and_budget_tight",
                inputs={"surrogate_error": 0.03, "budget_pressure": 0.92},
                thresholds={"max_error": 0.05, "min_pressure": 0.8},
                evidence={"rolling_window": 20},
                outcome={"mode": "surrogate"},
            )
        return None


def build_solver(steps: int = 12, run_id: str = "decision_trace_demo"):
    problem = Sphere()
    pipeline = RepresentationPipeline(
        initializer=UniformInitializer(low=problem.low, high=problem.high),
        mutator=ContextGaussianMutation(base_sigma=0.4, low=problem.low, high=problem.high),
        repair=ClipRepair(low=problem.low, high=problem.high),
    )
    adapter = SimulatedAnnealingAdapter(SAConfig(batch_size=8, initial_temperature=6.0, cooling_rate=0.96))
    solver = ComposableSolver(problem=problem, adapter=adapter, representation_pipeline=pipeline)
    solver.set_max_steps(int(steps))
    solver.add_plugin(DecisionTracePlugin(config=DecisionTraceConfig(output_dir="runs", run_id=run_id)))
    solver.add_plugin(DecisionSignalPlugin())
    return solver


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--steps", type=int, default=12)
    parser.add_argument("--run-id", type=str, default="decision_trace_demo")
    args = parser.parse_args()

    solver = build_solver(steps=args.steps, run_id=args.run_id)
    result = solver.run()
    trace_path = Path("runs") / f"{args.run_id}.decision_trace.jsonl"
    print("status:", result.get("status"), "steps:", result.get("steps"), "best:", float(solver.best_objective))
    print("trace:", trace_path)

    engine = DecisionReplayEngine.from_jsonl(trace_path)
    print("summary:", engine.summary())
    print("replay checks:")
    for evt in ("fallback", "inner_budget", "surrogate_trigger"):
        rows = list(engine.iter(event_type=evt))
        if rows:
            e = rows[-1]
            print(
                f"  gen={e.get('generation')} type={e.get('event_type')} "
                f"decision={e.get('decision')} reason={e.get('reason_code')}"
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
