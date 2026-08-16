"""Plugin gallery demo: choose plugins by catalog key and materialize runtime surface."""

import argparse
from datetime import datetime

import numpy as np

try:
    from nsgablack.adapters import SAConfig, SimulatedAnnealingAdapter
    from nsgablack.catalog import get_catalog
    from nsgablack.core.base import BlackBoxProblem
    from nsgablack.core.composable_solver import ComposableSolver
    from nsgablack.experiment.db import experiment_db_config_info
    from nsgablack.plugins import (
        ModuleReportConfig,
        ModuleReportPlugin,
        RuntimeSurfaceTrackerConfig,
        RuntimeSurfaceTrackerPlugin,
    )
    from nsgablack.representation import RepresentationPipeline
    from nsgablack.representation.continuous import ClipRepair, ContextGaussianMutation, UniformInitializer
except ModuleNotFoundError:  # pragma: no cover
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from nsgablack.adapters import SAConfig, SimulatedAnnealingAdapter
    from nsgablack.catalog import get_catalog
    from nsgablack.core.base import BlackBoxProblem
    from nsgablack.core.composable_solver import ComposableSolver
    from nsgablack.experiment.db import experiment_db_config_info
    from nsgablack.plugins import (
        ModuleReportConfig,
        ModuleReportPlugin,
        RuntimeSurfaceTrackerConfig,
        RuntimeSurfaceTrackerPlugin,
    )
    from nsgablack.representation import RepresentationPipeline
    from nsgablack.representation.continuous import ClipRepair, ContextGaussianMutation, UniformInitializer


class Sphere(BlackBoxProblem):
    def __init__(self, dimension: int = 6, low: float = -5.0, high: float = 5.0):
        super().__init__(name="Sphere", dimension=dimension, bounds={f"x{i}": (low, high) for i in range(dimension)})
        self.low = low
        self.high = high

    def evaluate(self, candidate):
        candidate = np.asarray(candidate, dtype=float)
        return float(np.sum(candidate * candidate))


def _default_demo_run_id(runtime_tag: str) -> str:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_tag = str(runtime_tag or "demo").strip().replace(" ", "_")
    return f"plugin_gallery_{safe_tag}_{stamp}"


def _load_plugin(key: str, *, runtime_tag: str = "demo"):
    normalized = str(key or "").strip()
    if normalized in {"plugin.module_report", "module_report"}:
        return ModuleReportPlugin(
            config=ModuleReportConfig(
                output_dir="runs",
                run_id=_default_demo_run_id(runtime_tag),
                write_bias_markdown=False,
            )
        )

    cat = get_catalog()
    entry = cat.get(normalized) or cat.get(f"plugin.{normalized}")
    if entry is None:
        raise KeyError(f"Unknown plugin key: {normalized}")
    cls = entry.load()
    try:
        return cls()
    except TypeError:
        return cls(name=entry.key.split(".")[-1])


def build_solver(
    plugin_keys,
    steps: int = 40,
    *,
    enable_runtime_surface: bool = True,
    runtime_db_path: str | None = None,
    runtime_namespace: str = "examples.plugin_gallery",
    runtime_tag: str = "demo",
):
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
        plugin = _load_plugin(key, runtime_tag=runtime_tag)
        solver.add_plugin(plugin)

    if enable_runtime_surface:
        runtime_cfg = RuntimeSurfaceTrackerConfig(
            db_path=runtime_db_path,
            namespace=runtime_namespace,
            tag=runtime_tag,
        )
        solver.add_plugin(RuntimeSurfaceTrackerPlugin(config=runtime_cfg))

    return solver


def _list_plugins():
    cat = get_catalog()
    keys = [e.key for e in cat.list(kind="plugin")]
    keys.sort()
    print("Available plugin keys:")
    for k in keys:
        print("-", k)
    print("- plugin.module_report (recommended for stable runtime run ids in this demo)")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--plugins",
        default="plugin.module_report,plugin.benchmark_harness",
        help="comma-separated plugin keys",
    )
    parser.add_argument("--steps", type=int, default=40)
    parser.add_argument(
        "--runtime-surface",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Materialize RuntimeSurfaceTrackerPlugin output into the resolved experiment DB target.",
    )
    parser.add_argument(
        "--runtime-db",
        default=None,
        help="Optional runtime surface DB target. Accepts a sqlite path or postgresql://... URL. Defaults to experiment/db.toml, env, and fallback protocol.",
    )
    parser.add_argument("--runtime-namespace", default="examples.plugin_gallery")
    parser.add_argument("--runtime-tag", default="demo")
    parser.add_argument("--list", action="store_true")
    args = parser.parse_args()

    if args.list:
        _list_plugins()
        return 0

    keys = [k.strip() for k in args.plugins.split(",") if k.strip()]
    solver = build_solver(
        keys,
        steps=args.steps,
        enable_runtime_surface=bool(args.runtime_surface),
        runtime_db_path=args.runtime_db,
        runtime_namespace=str(args.runtime_namespace),
        runtime_tag=str(args.runtime_tag),
    )
    result = solver.run()
    print("status:", result["status"], "steps:", result["steps"])
    print("best:", solver.best_objective)
    if bool(args.runtime_surface):
        artifacts = result.get("artifacts", {}) if isinstance(result, dict) else {}
        db_target = artifacts.get("runtime_surface_db") or experiment_db_config_info().get("db_target")
        run_ref = artifacts.get("runtime_surface_run_ref")
        print("runtime surface db:", db_target)
        print("runtime surface run ref:", run_ref or "-")
        if db_target:
            print(f"open dashboard: python -m nsgablack experiment ui --db \"{db_target}\"")
        else:
            print("open dashboard: python -m nsgablack experiment ui")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
