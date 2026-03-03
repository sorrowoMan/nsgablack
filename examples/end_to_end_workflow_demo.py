"""
End-to-end workflow demo:

One problem -> pipeline -> (optional) bias -> solver -> choose strategy via suites
-> attach benchmark harness -> run -> compare outputs.

Run (recommended):
  python examples/end_to_end_workflow_demo.py

If you did NOT install editable, run from repo root with:
  $env:PYTHONPATH=".."
  python examples/end_to_end_workflow_demo.py
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
    # Repo layout: this repository root is the Python package directory itself.
    # So we need to add the *parent* of repo root into sys.path.
    repo_parent = str(here.parent.parent.parent)
    if repo_parent not in sys.path:
        sys.path.insert(0, repo_parent)


_ensure_importable()

from nsgablack.core.base import BlackBoxProblem  # noqa: E402
from nsgablack.core.composable_solver import ComposableSolver  # noqa: E402
from nsgablack.adapters import (  # noqa: E402
    MultiStrategyConfig,
    MultiStrategyControllerAdapter,
    RoleSpec,
    VNSAdapter,
    VNSConfig,
    SimulatedAnnealingAdapter,
    SAConfig,
)
from nsgablack.representation import RepresentationPipeline  # noqa: E402
from nsgablack.representation.continuous import (  # noqa: E402
    UniformInitializer,
    ContextGaussianMutation,
    ClipRepair,
)
from nsgablack.utils.suites import (  # noqa: E402
    attach_benchmark_harness,
    attach_vns,
    attach_multi_strategy_coop,
)


class DemoSphere(BlackBoxProblem):
    def __init__(self, dim: int = 6):
        bounds = {f"x{i}": [-5.0, 5.0] for i in range(dim)}
        super().__init__(name="demo_sphere", dimension=dim, bounds=bounds, objectives=["min"])

    def evaluate(self, x):
        x = np.asarray(x, dtype=float)
        if x.ndim > 1:
            return np.sum(x * x, axis=1)
        return float(np.sum(x * x))


def build_pipeline(problem: DemoSphere) -> RepresentationPipeline:
    return RepresentationPipeline(
        initializer=UniformInitializer(low=-5.0, high=5.0),
        mutator=ContextGaussianMutation(base_sigma=0.6, sigma_key="mutation_sigma"),
        repair=ClipRepair(low=-5.0, high=5.0),
    )


def run_baseline_vns(*, out_dir: str, seed: int = 42) -> None:
    np.random.seed(seed)
    problem = DemoSphere()
    pipeline = build_pipeline(problem)

    solver = ComposableSolver(problem=problem, representation_pipeline=pipeline)
    attach_vns(solver, config=VNSConfig(batch_size=32, k_max=4))
    attach_benchmark_harness(solver, output_dir=out_dir, run_id="baseline_vns", seed=seed, overwrite=True)

    solver.set_max_steps(40)
    solver.run()
    print(f"[baseline_vns] done -> {out_dir}")


def run_coop_phase_regions(*, out_dir: str, seed: int = 42) -> None:
    np.random.seed(seed)
    problem = DemoSphere()
    pipeline = build_pipeline(problem)

    # Two roles:
    # - explorer: SA (more random / temperature-driven exploration)
    # - exploiter: VNS (local refinement)
    roles = [
        RoleSpec(
            name="explorer",
            adapter=lambda uid: SimulatedAnnealingAdapter(SAConfig(batch_size=8)),
            n_units=8,
            weight=1.0,
        ),
        RoleSpec(
            name="exploiter",
            adapter=lambda uid: VNSAdapter(VNSConfig(batch_size=8, k_max=4)),
            n_units=4,
            weight=1.0,
        ),
    ]

    cfg = MultiStrategyConfig(
        total_batch_size=96,
        # macro-serial phases; micro-parallel units inside each phase
        phase_schedule=(("explore", 15), ("exploit", -1)),
        phase_roles={"explore": ["explorer"], "exploit": ["exploiter"]},
        enable_regions=True,
        n_regions=8,
        region_update_interval=5,
        seeds_per_task=2,
        seeds_source="pareto",
    )

    solver = ComposableSolver(problem=problem, representation_pipeline=pipeline)
    attach_multi_strategy_coop(solver, roles=roles, config=cfg, attach_pareto_archive=True)
    attach_benchmark_harness(solver, output_dir=out_dir, run_id="coop_phase_regions", seed=seed, overwrite=True)

    solver.set_max_steps(40)
    solver.run()
    print(f"[coop_phase_regions] done -> {out_dir}")


def main() -> None:
    out_dir = os.path.abspath(os.path.join("runs", "end_to_end_demo"))
    os.makedirs(out_dir, exist_ok=True)

    run_baseline_vns(out_dir=out_dir, seed=123)
    run_coop_phase_regions(out_dir=out_dir, seed=123)

    print("")
    print("Outputs:")
    print(f"  {out_dir}{os.sep}baseline_vns.csv")
    print(f"  {out_dir}{os.sep}baseline_vns.summary.json")
    print(f"  {out_dir}{os.sep}coop_phase_regions.csv")
    print(f"  {out_dir}{os.sep}coop_phase_regions.summary.json")


if __name__ == "__main__":
    main()
