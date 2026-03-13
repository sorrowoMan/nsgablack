"""Usable nested example: optimize production SUPPLY.xlsx by event-level early shifts.

Outer layer:
- decision variables are shift days for each non-zero supply event (day>0)

Inner layer:
- production evaluation model computes output under adjusted supply

Rules enforced:
- day0 fixed
- only early shift (no delay)
- whole-event move (no split)
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

from nsgablack.core.evolution_solver import EvolutionSolver  # noqa: E402
from nsgablack.utils.parallel import with_parallel_evaluation  # noqa: E402
from nsgablack.utils.wiring import attach_default_observability_plugins  # noqa: E402
from nsgablack.utils.viz import launch_from_builder  # noqa: E402

from evaluation import ProductionInnerEvalConfig, ProductionInnerEvaluationModel
from plugins import SupplyAdjustmentExportPlugin
from problem import SupplyEventShiftProblem


def _resolve_default_baseline_plan(base_dir: Path) -> Optional[Path]:
    cases_dir = base_dir.parent
    export_dirs = (
        cases_dir,
        cases_dir / "runs" / "production_schedule" / "exports",
    )
    cands = []
    for d in export_dirs:
        if d.exists():
            cands.extend(d.glob("integrated_result_production_*.xlsx"))
    cands = sorted(cands, reverse=True)
    return cands[0] if cands else None


def _load_baseline_schedule(path: Path, *, machines: int, days: int) -> np.ndarray:
    import pandas as pd

    df = pd.read_excel(path, sheet_name=0)
    machine_cols = [c for c in df.columns if str(c).startswith("Machine") or str(c).startswith("机种")]
    if not machine_cols:
        machine_cols = list(df.columns[2:])
    arr = df[machine_cols].to_numpy(dtype=float)
    if arr.shape == (days, machines):
        return arr.T
    if arr.shape == (machines, days):
        return arr
    out = np.zeros((machines, days), dtype=float)
    r = min(machines, arr.shape[0])
    c = min(days, arr.shape[1])
    out[:r, :c] = arr[:r, :c]
    return out


def _load_case_data(base_dir: Path, bom: Optional[str], supply: Optional[str], *, machines: int, materials: int, days: int):
    """Reuse production_scheduling data loader for BOM/SUPPLY parsing."""
    prod_case_dir = (base_dir.parent / "production_scheduling").resolve()
    if str(prod_case_dir) not in sys.path:
        sys.path.insert(0, str(prod_case_dir))

    from refactor_data import load_production_data  # type: ignore

    data = load_production_data(
        base_dir=prod_case_dir,
        bom_path=Path(bom) if bom else None,
        supply_path=Path(supply) if supply else None,
        machines=int(machines),
        materials=int(materials),
        days=int(days),
        fallback=False,
    )
    if getattr(data, "bom_path", None) is None or getattr(data, "supply_path", None) is None:
        raise RuntimeError("BOM/SUPPLY not resolved; provide --bom and --supply explicitly.")
    print(f"[data] bom={data.bom_path}")
    print(f"[data] supply={data.supply_path}")
    return data


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Supply adjustment by event-level early shifts (nested evaluation)")
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--machines", type=int, default=22)
    p.add_argument("--materials", type=int, default=157)
    p.add_argument("--days", type=int, default=31)

    p.add_argument("--bom", type=str, default=None)
    p.add_argument("--supply", type=str, default=None)
    p.add_argument("--baseline-plan", type=str, default=None, help="Baseline production plan xlsx for residual inner eval.")
    p.add_argument("--max-active-machines", type=int, default=8)
    p.add_argument("--max-production-per-machine", type=float, default=3000.0)
    p.add_argument("--inner-eval-mode", type=str, default="hybrid", choices=["integrated", "hybrid", "fast"])
    p.add_argument("--inner-trials", type=int, default=6)
    p.add_argument("--hybrid-top-quantile", type=float, default=0.85)
    p.add_argument("--hybrid-explore-prob", type=float, default=0.05)
    p.add_argument("--hybrid-random-refine-ratio", type=float, default=0.10)
    p.add_argument("--hybrid-warmup", type=int, default=20)
    p.add_argument("--hybrid-refine-pop-size", type=int, default=24)
    p.add_argument("--hybrid-refine-generations", type=int, default=3)
    p.add_argument("--hybrid-no-rf", action="store_true")
    p.add_argument("--hybrid-rf-uncertainty-quantile", type=float, default=0.90)
    p.add_argument("--hybrid-rf-min-samples", type=int, default=40)
    p.add_argument("--hybrid-rf-retrain-interval", type=int, default=10)
    p.add_argument("--hybrid-rf-max-train-samples", type=int, default=2000)
    p.add_argument("--hybrid-rf-n-estimators", type=int, default=96)
    p.add_argument("--max-moved-events", type=int, default=200, help="Hard cap on moved supply events (<=0 to disable).")

    p.add_argument("--pop-size", type=int, default=60)
    p.add_argument("--generations", type=int, default=40)

    p.add_argument("--parallel", action="store_true")
    p.add_argument("--parallel-backend", type=str, default="thread", choices=["thread", "process", "ray", "joblib", "auto"])
    p.add_argument("--parallel-workers", type=int, default=8)
    p.add_argument("--parallel-thread-bias-isolation", type=str, default="off", choices=["off", "disable_cache", "deepcopy"])
    p.add_argument("--parallel-strict", action="store_true")

    p.add_argument("--run-id", type=str, default=None)
    p.add_argument("--run-dir", type=str, default="runs/supply_adjustment_nested")
    p.add_argument("--no-decision-trace", action="store_true")
    p.add_argument("--no-profiler", action="store_true")
    p.add_argument("--ui", action="store_true")
    return p


def _build_solver_from_args(args):
    if int(getattr(args, "days", 31)) != 31:
        print(f"[run] override --days={args.days} ignored; enforcing 31-day window (day0..30).")
    args.days = 31
    random.seed(args.seed)
    np.random.seed(args.seed)

    data = _load_case_data(
        _THIS_DIR,
        args.bom,
        args.supply,
        machines=args.machines,
        materials=args.materials,
        days=args.days,
    )

    baseline_plan_path = Path(args.baseline_plan) if getattr(args, "baseline_plan", None) else _resolve_default_baseline_plan(_THIS_DIR)
    baseline_schedule = None
    if baseline_plan_path is not None and baseline_plan_path.exists():
        baseline_schedule = _load_baseline_schedule(
            baseline_plan_path,
            machines=int(args.machines),
            days=int(args.days),
        )
        print(f"[data] baseline_plan={baseline_plan_path}")

    inner_model = ProductionInnerEvaluationModel(
        bom_matrix=np.asarray(data.bom_matrix, dtype=float),
        base_supply=np.asarray(data.supply_matrix, dtype=float),
        production_case_dir=(_THIS_DIR.parent / "production_scheduling").resolve(),
        baseline_schedule=baseline_schedule,
        cfg=ProductionInnerEvalConfig(
            mode=str(args.inner_eval_mode),
            max_active_machines_per_day=int(args.max_active_machines),
            max_production_per_machine=float(args.max_production_per_machine),
            inner_trials=int(args.inner_trials),
            hybrid_top_quantile=float(args.hybrid_top_quantile),
            hybrid_explore_prob=float(args.hybrid_explore_prob),
            hybrid_random_refine_ratio=float(args.hybrid_random_refine_ratio),
            hybrid_warmup=int(args.hybrid_warmup),
            hybrid_refine_pop_size=int(args.hybrid_refine_pop_size),
            hybrid_refine_generations=int(args.hybrid_refine_generations),
            hybrid_rf_enable=not bool(args.hybrid_no_rf),
            hybrid_rf_uncertainty_quantile=float(args.hybrid_rf_uncertainty_quantile),
            hybrid_rf_min_samples=int(args.hybrid_rf_min_samples),
            hybrid_rf_retrain_interval=int(args.hybrid_rf_retrain_interval),
            hybrid_rf_max_train_samples=int(args.hybrid_rf_max_train_samples),
            hybrid_rf_n_estimators=int(args.hybrid_rf_n_estimators),
        ),
    )

    problem = SupplyEventShiftProblem(
        base_supply=np.asarray(data.supply_matrix, dtype=float),
        inner_model=inner_model,
        material_ids=np.arange(1, int(args.materials) + 1),
        max_moved_events=(None if int(args.max_moved_events) <= 0 else int(args.max_moved_events)),
    )

    print(f"[outer] adjustable_events={problem.dimension} materials={problem.materials} days=31")
    print("[window] production_window=day0..30 adjustable_supply_event_day_range=1..30")
    print(
        f"[inner] mode={args.inner_eval_mode} trials={args.inner_trials} "
        f"q={args.hybrid_top_quantile} ratio={args.hybrid_random_refine_ratio} p={args.hybrid_explore_prob} "
        f"refine=({args.hybrid_refine_pop_size},{args.hybrid_refine_generations}) "
        f"rf={'off' if args.hybrid_no_rf else 'on'}(q={args.hybrid_rf_uncertainty_quantile},"
        f"min={args.hybrid_rf_min_samples},interval={args.hybrid_rf_retrain_interval}) "
        f"max_moved_events={('off' if int(args.max_moved_events) <= 0 else int(args.max_moved_events))}"
    )
    if int(args.max_moved_events) <= 0:
        print("[constraint] max_moved_events=off (no hard cap)")
    else:
        print(f"[constraint] max_moved_events<={int(args.max_moved_events)} (hard cap enabled)")

    SolverCls = with_parallel_evaluation(EvolutionSolver)
    solver = SolverCls(
        problem,
        pop_size=int(args.pop_size),
        max_generations=int(args.generations),
        enable_parallel=bool(args.parallel),
        parallel_backend=args.parallel_backend,
        parallel_max_workers=int(args.parallel_workers),
        parallel_thread_bias_isolation=args.parallel_thread_bias_isolation,
        parallel_strict=bool(args.parallel_strict),
    )

    run_id = args.run_id or datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir = Path(args.run_dir)
    run_dir.mkdir(parents=True, exist_ok=True)

    attach_default_observability_plugins(
        solver,
        output_dir=str(run_dir),
        run_id=str(run_id),
        enable_decision_trace=not bool(args.no_decision_trace),
        enable_profiler=not bool(args.no_profiler),
    )
    solver.add_plugin(SupplyAdjustmentExportPlugin(case_problem=problem, output_dir=run_dir, run_id=run_id))
    # Route inner-eval stage decisions into DecisionTrace when plugin is enabled.
    def _inner_decision_sink(**event_kwargs):
        fn = getattr(solver, "record_decision_event", None)
        if callable(fn):
            return fn(**event_kwargs)
        return None

    inner_model.decision_sink = _inner_decision_sink
    return solver


def build_solver(argv: Optional[list] = None):
    args = build_parser().parse_args(argv if argv is not None else [])
    return _build_solver_from_args(args)


def main(argv: Optional[list] = None) -> None:
    args = build_parser().parse_args(argv)
    if bool(args.ui):
        launch_from_builder(lambda: _build_solver_from_args(args), entry_label="working_nested_optimizer.py:build_solver")
        return

    solver = _build_solver_from_args(args)
    result = solver.run()

    if isinstance(result, dict):
        status = result.get("status", "unknown")
        steps = result.get("steps_executed", "-")
        best = result.get("best_objective", "-")
    else:
        status = getattr(result, "status", "completed")
        steps = getattr(result, "steps_executed", getattr(result, "steps", "-"))
        best = getattr(result, "best_objective", getattr(solver, "best_objective", "-"))
    print(f"done: status={status} steps={steps} best={best}")


if __name__ == "__main__":
    main()
