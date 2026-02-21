"""
Surrogate evaluation plugin demo.

Goal:
- show how a capability-layer Plugin can reduce expensive true evaluations
  without changing adapters/pipelines.

Run:
  python examples/surrogate_plugin_demo.py

If you did NOT install editable, run from repo root with:
  $env:PYTHONPATH=".."
  python examples/surrogate_plugin_demo.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import numpy as np


def _ensure_importable() -> None:
    try:
        import nsgablack  # noqa: F401
        return
    except Exception:
        pass
    here = Path(__file__).resolve()
    repo_parent = str(here.parent.parent.parent)
    if repo_parent not in sys.path:
        sys.path.insert(0, repo_parent)


_ensure_importable()

from nsgablack.core.base import BlackBoxProblem  # noqa: E402
from nsgablack.core.composable_solver import ComposableSolver  # noqa: E402
from nsgablack.representation import RepresentationPipeline  # noqa: E402
from nsgablack.representation.continuous import ClipRepair, GaussianMutation, UniformInitializer  # noqa: E402
from nsgablack.plugins import SurrogateEvaluationConfig, SurrogateEvaluationPlugin  # noqa: E402
from nsgablack.utils.suites import attach_benchmark_harness, attach_simulated_annealing  # noqa: E402


class ExpensiveSphere(BlackBoxProblem):
    """A toy "expensive" objective: still fast, but we count true evaluations."""

    def __init__(self, dim: int = 12):
        bounds = {f"x{i}": [-5.0, 5.0] for i in range(dim)}
        super().__init__(name="expensive_sphere", dimension=dim, bounds=bounds, objectives=["min"])

    def evaluate(self, x):
        x = np.asarray(x, dtype=float)
        # keep it deterministic and quick; pretend this is expensive
        return float(np.sum(x * x))


def _build_solver(*, enable_surrogate: bool, out_dir: str, run_id: str) -> ComposableSolver:
    problem = ExpensiveSphere()
    pipeline = RepresentationPipeline(
        initializer=UniformInitializer(low=-5.0, high=5.0),
        mutator=GaussianMutation(sigma=0.6),
        repair=ClipRepair(low=-5.0, high=5.0),
    )
    solver = ComposableSolver(problem=problem, representation_pipeline=pipeline)
    attach_simulated_annealing(solver, batch_size=48, initial_temperature=1.0, cooling_rate=0.95)
    attach_benchmark_harness(solver, output_dir=out_dir, run_id=run_id, seed=123, overwrite=True)

    if enable_surrogate:
        cfg = SurrogateEvaluationConfig(
            min_train_samples=24,
            min_true_evals=10,
            topk_exploit=8,
            topk_explore=8,
            retrain_every_call=True,
            objective_aggregation="sum",
            random_seed=123,
        )
        plugin = SurrogateEvaluationPlugin(config=cfg, model_type="rf", online_training=True)
        solver.add_plugin(plugin)
        # Stash on solver for easy access in this demo.
        solver._surrogate_plugin_demo_ref = plugin  # type: ignore[attr-defined]

    return solver


def main() -> None:
    out_dir = os.path.abspath(os.path.join("runs", "surrogate_plugin_demo"))
    os.makedirs(out_dir, exist_ok=True)

    # Baseline
    base = _build_solver(enable_surrogate=False, out_dir=out_dir, run_id="baseline_true_eval")
    base.set_max_steps(35)
    base.run()
    baseline_evals = int(getattr(base, "evaluation_count", 0) or 0)

    # With surrogate
    solver = _build_solver(enable_surrogate=True, out_dir=out_dir, run_id="surrogate_eval")
    solver.set_max_steps(35)
    solver.run()
    total_evals = int(getattr(solver, "evaluation_count", 0) or 0)

    # Plugin stats
    plugin = getattr(solver, "_surrogate_plugin_demo_ref", None)

    print("done.")
    print(f"baseline evaluation_count (true): {baseline_evals}")
    if plugin is not None:
        print("surrogate plugin stats:", plugin.stats)
    print(f"solver evaluation_count (true): {total_evals}")
    print("outputs:")
    print(f"  {out_dir}{os.sep}baseline_true_eval.csv")
    print(f"  {out_dir}{os.sep}baseline_true_eval.summary.json")
    print(f"  {out_dir}{os.sep}surrogate_eval.csv")
    print(f"  {out_dir}{os.sep}surrogate_eval.summary.json")


if __name__ == "__main__":
    main()

