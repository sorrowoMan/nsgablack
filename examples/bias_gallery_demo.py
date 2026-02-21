"""Bias gallery demo: choose a bias by catalog key and run a tiny solver."""

import argparse
import numpy as np

try:
    from nsgablack.catalog import get_catalog
    from nsgablack.core.base import BlackBoxProblem
    from nsgablack.core.composable_solver import ComposableSolver
    from nsgablack.core.adapters import SimulatedAnnealingAdapter, SAConfig
    from nsgablack.representation import RepresentationPipeline
    from nsgablack.representation.continuous import UniformInitializer, ContextGaussianMutation, ClipRepair
    from nsgablack.bias import BiasModule
    from nsgablack.bias.domain import DynamicPenaltyBias
    from nsgablack.bias.domain.callable_bias import CallableBias
    from nsgablack.utils.suites import attach_benchmark_harness, attach_module_report
except ModuleNotFoundError:  # pragma: no cover
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from nsgablack.catalog import get_catalog
    from nsgablack.core.base import BlackBoxProblem
    from nsgablack.core.composable_solver import ComposableSolver
    from nsgablack.core.adapters import SimulatedAnnealingAdapter, SAConfig
    from nsgablack.representation import RepresentationPipeline
    from nsgablack.representation.continuous import UniformInitializer, ContextGaussianMutation, ClipRepair
    from nsgablack.bias import BiasModule
    from nsgablack.bias.domain import DynamicPenaltyBias
    from nsgablack.bias.domain.callable_bias import CallableBias
    from nsgablack.utils.suites import attach_benchmark_harness, attach_module_report


class Sphere(BlackBoxProblem):
    def __init__(self, dimension=8, low=-5.0, high=5.0):
        super().__init__(name="Sphere", dimension=dimension, bounds={f"x{i}": (low, high) for i in range(dimension)})
        self.low = low
        self.high = high

    def evaluate(self, x):
        x = np.asarray(x, dtype=float)
        return float(np.sum(x * x))


def _make_bias(key: str, dimension: int):
    cat = get_catalog()
    entry = cat.get(key) or cat.get(f"bias.{key}")
    if entry is None:
        raise KeyError(f"Unknown bias key: {key}")

    cls = entry.load()

    if entry.key == "bias.dynamic_penalty":
        def penalty_func(x, _context):
            x = np.asarray(x, dtype=float)
            return float(max(0.0, np.sum(x) - 1.0))

        return cls(penalty_func=penalty_func, weight=0.2)

    if entry.key == "bias.callable":
        return CallableBias("callable_rule", func=lambda x, _ctx=None: float(np.sum(x)) * 0.0)

    try:
        return cls()
    except TypeError:
        # Last-resort: try with a generic weight
        return cls(weight=0.2)


def build_solver(bias_key: str, steps: int = 40):
    problem = Sphere()

    pipeline = RepresentationPipeline(
        initializer=UniformInitializer(low=problem.low, high=problem.high),
        mutator=ContextGaussianMutation(base_sigma=0.4, low=problem.low, high=problem.high),
        repair=ClipRepair(low=problem.low, high=problem.high),
    )

    bias_module = BiasModule()
    bias_module.add(_make_bias(bias_key, problem.dimension))

    adapter = SimulatedAnnealingAdapter(SAConfig(batch_size=8, initial_temperature=6.0, cooling_rate=0.96))

    solver = ComposableSolver(
        problem=problem,
        adapter=adapter,
        representation_pipeline=pipeline,
        bias_module=bias_module,
    )
    solver.set_enable_bias(True)
    solver.set_max_steps(int(steps))

    attach_benchmark_harness(solver, output_dir="runs", run_id="bias_gallery", overwrite=True, log_every=1)
    attach_module_report(solver, output_dir="runs", run_id="bias_gallery", write_bias_markdown=True)
    return solver


def _list_biases():
    cat = get_catalog()
    keys = [e.key for e in cat.list(kind="bias")]
    keys.sort()
    print("Available bias keys:")
    for k in keys:
        print("-", k)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--bias", default="bias.dynamic_penalty", help="bias key (e.g., bias.dynamic_penalty)")
    parser.add_argument("--steps", type=int, default=40)
    parser.add_argument("--list", action="store_true")
    args = parser.parse_args()

    if args.list:
        _list_biases()
        return 0

    solver = build_solver(args.bias, steps=args.steps)
    result = solver.run()
    print("status:", result["status"], "steps:", result["steps"])
    print("best:", solver.best_objective)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
