"""Plugin gallery demo: choose plugins by catalog key and run a tiny solver."""

import argparse
import numpy as np

try:
    from nsgablack.catalog import get_catalog
    from nsgablack.core.base import BlackBoxProblem
    from nsgablack.core.composable_solver import ComposableSolver
    from nsgablack.core.adapters import SimulatedAnnealingAdapter, SAConfig
    from nsgablack.representation import RepresentationPipeline
    from nsgablack.representation.continuous import UniformInitializer, ContextGaussianMutation, ClipRepair
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


class Sphere(BlackBoxProblem):
    def __init__(self, dimension=6, low=-5.0, high=5.0):
        super().__init__(name="Sphere", dimension=dimension, bounds={f"x{i}": (low, high) for i in range(dimension)})
        self.low = low
        self.high = high

    def evaluate(self, x):
        x = np.asarray(x, dtype=float)
        return float(np.sum(x * x))


def _load_plugin(key: str):
    cat = get_catalog()
    entry = cat.get(key) or cat.get(f"plugin.{key}")
    if entry is None:
        raise KeyError(f"Unknown plugin key: {key}")
    cls = entry.load()
    try:
        return cls()
    except TypeError:
        return cls(name=entry.key.split(".")[-1])


def build_solver(plugin_keys, steps: int = 40):
    problem = Sphere()

    pipeline = RepresentationPipeline(
        initializer=UniformInitializer(low=problem.low, high=problem.high),
        mutator=ContextGaussianMutation(base_sigma=0.4, low=problem.low, high=problem.high),
        repair=ClipRepair(low=problem.low, high=problem.high),
    )

    adapter = SimulatedAnnealingAdapter(SAConfig(batch_size=8, initial_temperature=6.0, cooling_rate=0.96))
    solver = ComposableSolver(problem=problem, adapter=adapter, representation_pipeline=pipeline)
    solver.set_max_steps(int(steps))

    for key in plugin_keys:
        plugin = _load_plugin(key)
        solver.add_plugin(plugin)

    # Optional: you can add BenchmarkHarnessPlugin via --plugins if needed.
    return solver


def _list_plugins():
    cat = get_catalog()
    keys = [e.key for e in cat.list(kind="plugin")]
    keys.sort()
    print("Available plugin keys:")
    for k in keys:
        print("-", k)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--plugins", default="plugin.module_report,plugin.benchmark_harness", help="comma-separated plugin keys")
    parser.add_argument("--steps", type=int, default=40)
    parser.add_argument("--list", action="store_true")
    args = parser.parse_args()

    if args.list:
        _list_plugins()
        return 0

    keys = [k.strip() for k in args.plugins.split(",") if k.strip()]
    solver = build_solver(keys, steps=args.steps)
    result = solver.run()
    print("status:", result["status"], "steps:", result["steps"])
    print("best:", solver.best_objective)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
