from __future__ import annotations

"""
5-minute minimal reproducible run script.

Purpose:
- Quickly validate that the framework runs end-to-end on a clean environment.
- Produce deterministic-ish artifacts for issue reports.
"""

from pathlib import Path

import numpy as np

from nsgablack.core.base import BlackBoxProblem
from nsgablack.adapters import SAConfig, SimulatedAnnealingAdapter
from nsgablack.core.composable_solver import ComposableSolver
from nsgablack.plugins import BenchmarkHarnessConfig, BenchmarkHarnessPlugin, ModuleReportConfig, ModuleReportPlugin
from nsgablack.representation import RepresentationPipeline
from nsgablack.representation.continuous import ClipRepair, ContextGaussianMutation, UniformInitializer


class _MinProblem(BlackBoxProblem):
    def __init__(self, dimension: int = 8) -> None:
        bounds = {f"x{i}": [-5.0, 5.0] for i in range(dimension)}
        super().__init__(
            name="MinReproProblem",
            dimension=dimension,
            bounds=bounds,
            objectives=["sphere", "l1"],
        )

    def evaluate(self, x):
        arr = np.asarray(x, dtype=float).reshape(-1)
        return np.array([float(np.sum(arr**2)), float(np.sum(np.abs(arr)))], dtype=float)

    def evaluate_constraints(self, x):
        _ = x
        return np.zeros(0, dtype=float)


def main() -> int:
    out_dir = Path("runs/min_repro_5min")
    out_dir.mkdir(parents=True, exist_ok=True)

    problem = _MinProblem(dimension=8)
    pipeline = RepresentationPipeline(
        initializer=UniformInitializer(low=-5.0, high=5.0),
        mutator=ContextGaussianMutation(base_sigma=0.2, sigma_key="mutation_sigma"),
        repair=ClipRepair(low=-5.0, high=5.0),
    )

    solver = ComposableSolver(
        problem=problem,
        adapter=SimulatedAnnealingAdapter(SAConfig(batch_size=8)),
        representation_pipeline=pipeline,
    )
    solver.max_steps = 40
    solver.set_random_seed(20260222)
    solver.add_plugin(
        BenchmarkHarnessPlugin(
            config=BenchmarkHarnessConfig(
                output_dir=str(out_dir),
                run_id="min_repro_5min",
                overwrite=True,
                log_every=1,
            )
        )
    )
    solver.add_plugin(
        ModuleReportPlugin(
            config=ModuleReportConfig(
                output_dir=str(out_dir),
                run_id="min_repro_5min",
                overwrite=True,
            )
        )
    )
    result = solver.run(return_dict=True)
    print(f"[ok] status={result.get('status')} steps={result.get('steps')} best={result.get('best_objective')}")
    print(f"[ok] artifacts_dir={out_dir.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
