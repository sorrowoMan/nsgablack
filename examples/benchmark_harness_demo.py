"""
Benchmark harness demo (unified experiment protocol).

Run:
  python examples/benchmark_harness_demo.py

If you did NOT install editable, run from repo root with:
  $env:PYTHONPATH=".."
  python examples/benchmark_harness_demo.py
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
from nsgablack.representation.continuous import ClipRepair, UniformInitializer  # noqa: E402
from nsgablack.representation.continuous import GaussianMutation  # noqa: E402
from nsgablack.utils.suites import attach_benchmark_harness, attach_simulated_annealing  # noqa: E402


class DemoSphere(BlackBoxProblem):
    def __init__(self, dim: int = 8):
        bounds = {f"x{i}": [-5.0, 5.0] for i in range(dim)}
        super().__init__(name="demo_sphere", dimension=dim, bounds=bounds, objectives=["min"])

    def evaluate(self, x):
        x = np.asarray(x, dtype=float)
        return float(np.sum(x * x))


def main() -> None:
    out_dir = os.path.abspath(os.path.join("runs", "benchmark_harness_demo"))
    os.makedirs(out_dir, exist_ok=True)

    problem = DemoSphere()
    pipeline = RepresentationPipeline(
        initializer=UniformInitializer(low=-5.0, high=5.0),
        mutator=GaussianMutation(sigma=0.7),
        repair=ClipRepair(low=-5.0, high=5.0),
    )

    solver = ComposableSolver(problem=problem, representation_pipeline=pipeline)
    attach_simulated_annealing(solver, batch_size=32, initial_temperature=1.0, cooling_rate=0.92)
    attach_benchmark_harness(
        solver,
        output_dir=out_dir,
        run_id="sa_with_harness",
        seed=123,
        overwrite=True,
    )

    solver.max_steps = 40
    result = solver.run()

    print("done.")
    print("result.status:", result.get("status"))
    print("outputs:")
    print(f"  {out_dir}{os.sep}sa_with_harness.csv")
    print(f"  {out_dir}{os.sep}sa_with_harness.summary.json")


if __name__ == "__main__":
    main()
