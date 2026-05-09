# -*- coding: utf-8 -*-
"""Case entry: outer nsgablack scaffold + inner mlblack scaffold.

Design:
- Outer layer: nsgablack EvolutionSolver standard assembly.
- Inner layer: mlblack run_train_flow standard assembly (xgboost trainer).
- No base framework modifications; this is a case-only composition.
"""

from __future__ import annotations

import argparse
import random
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

import numpy as np

_THIS_DIR = Path(__file__).resolve().parent
if str(_THIS_DIR) not in sys.path:
    sys.path.insert(0, str(_THIS_DIR))

from _bootstrap import ensure_nsgablack_importable  # noqa: E402

ensure_nsgablack_importable(Path(__file__))

from nsgablack.adapters import VNSAdapter, VNSConfig  # noqa: E402
from nsgablack.core.composable_solver import ComposableSolver  # noqa: E402
from nsgablack.plugins import BasicElitePlugin  # noqa: E402
from nsgablack.representation import RepresentationPipeline  # noqa: E402
from nsgablack.representation.continuous import (  # noqa: E402
    ClipRepair,
    ContextGaussianMutation,
    UniformInitializer,
)
from nsgablack.utils.wiring import attach_default_observability_plugins  # noqa: E402

from evaluation.inner_mlblack_runner import MlblackFlowRunner  # noqa: E402
from problem.outer_problem import MlblackNestedOuterProblem  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Outer nsgablack scaffold + inner mlblack scaffold case",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("--mlblack-root", type=str, default=r"C:\Users\hp\Desktop\mlblack")
    p.add_argument(
        "--csv-path",
        type=str,
        default=r"C:\Users\hp\Desktop\work\final_pipeline_package_20260402\04_interval_dataset\ci_interval_opt_table.csv",
    )
    p.add_argument("--fold-col", type=str, default="test_fold_1")
    p.add_argument("--target-col", type=str, default="ci")
    p.add_argument("--generations", type=int, default=6)
    p.add_argument("--batch-size", type=int, default=10)
    p.add_argument("--vns-k-max", type=int, default=4)
    p.add_argument("--vns-base-sigma", type=float, default=0.2)
    p.add_argument("--seed", type=int, default=7)
    p.add_argument("--run-id", type=str, default="")
    p.add_argument("--run-dir", type=str, default=str(_THIS_DIR / "runs" / "mlblack_nested"))
    p.add_argument("--no-logs", action="store_true")
    return p


def _build_solver_from_args(args):
    random.seed(int(args.seed))
    np.random.seed(int(args.seed))

    run_id = str(args.run_id or datetime.now().strftime("%Y%m%d_%H%M%S"))
    run_root = Path(args.run_dir).expanduser().resolve() / run_id
    inner_root = run_root / "inner_runs"

    inner = MlblackFlowRunner(
        mlblack_root=str(args.mlblack_root),
        csv_path=str(args.csv_path),
        fold_col=str(args.fold_col),
        target_col=str(args.target_col),
        output_root=str(inner_root),
        random_seed=int(args.seed),
    )
    problem = MlblackNestedOuterProblem(inner_runner=inner)

    lows = np.array([problem.bounds[f"x{i}"][0] for i in range(problem.dimension)], dtype=float)
    highs = np.array([problem.bounds[f"x{i}"][1] for i in range(problem.dimension)], dtype=float)
    pipeline = RepresentationPipeline(
        initializer=UniformInitializer(low=lows, high=highs),
        mutator=ContextGaussianMutation(
            base_sigma=float(args.vns_base_sigma),
            sigma_key="mutation_sigma",
            low=lows,
            high=highs,
        ),
        repair=ClipRepair(low=lows, high=highs),
    )
    adapter = VNSAdapter(
        VNSConfig(
            batch_size=max(4, int(args.batch_size)),
            k_max=max(1, int(args.vns_k_max)),
            base_sigma=float(args.vns_base_sigma),
            scale=1.6,
            objective_aggregation="sum",
        )
    )
    solver = ComposableSolver(
        problem=problem,
        adapter=adapter,
        representation_pipeline=pipeline,
    )
    solver.set_max_steps(int(args.generations))
    solver.add_plugin(BasicElitePlugin(retention_prob=0.9, retention_ratio=0.2))

    if not bool(args.no_logs):
        run_root.mkdir(parents=True, exist_ok=True)
        attach_default_observability_plugins(
            solver,
            output_dir=str(run_root),
            run_id=str(run_id),
            overwrite=True,
            enable_pareto_archive=False,
            enable_benchmark=True,
            benchmark_log_every=1,
            benchmark_flush_every=10,
            enable_module_report=True,
            write_bias_markdown=False,
            enable_profiler=False,
            enable_decision_trace=True,
            decision_trace_flush_every=1,
        )
    return solver


def build_solver(argv: Optional[list] = None):
    args = build_parser().parse_args(argv if argv is not None else [])
    return _build_solver_from_args(args)


def main(argv: Optional[list] = None) -> None:
    args = build_parser().parse_args(argv if argv is not None else None)
    solver = _build_solver_from_args(args)
    _ = solver.run()
    problem = solver.problem
    best_x = getattr(solver, "best_x", None)
    print(f"[case] status=completed steps={solver.generation}")
    if best_x is None:
        print("[case] no best solution found")
        return
    obj = problem.evaluate(best_x)
    params = problem._decode(best_x)  # case demo: inspect best configuration
    print(f"[case] best_rmse={float(obj[0]):.6f} complexity={float(obj[1]):.6f}")
    print(f"[case] best_params={params}")
    last_inner = getattr(problem, "last_inner", None)
    if last_inner is not None:
        print(
            f"[case] inner_metrics rmse={last_inner.rmse:.6f} "
            f"mae={last_inner.mae:.6f} r2={last_inner.r2:.6f} "
            f"elapsed={last_inner.elapsed_sec:.3f}s"
        )
    print(f"[case] fold={args.fold_col}")


if __name__ == "__main__":
    main()
