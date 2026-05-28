"""Formal L1/L2 nested assembly for event-level supply adjustment.

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

_THIS_DIR = Path(__file__).resolve().parents[1]
if str(_THIS_DIR) not in sys.path:
    sys.path.insert(0, str(_THIS_DIR))

from _bootstrap import ensure_nsgablack_importable  # noqa: E402

ensure_nsgablack_importable(Path(__file__))

from nsgablack.core.evolution_solver import EvolutionSolver  # noqa: E402
from nsgablack.core.nested_solver import InnerRuntimeConfig, TaskInnerRuntimeEvaluator  # noqa: E402
from nsgablack.core.resources import ResourceRequirement  # noqa: E402
from nsgablack.plugins import TimeoutBudgetConfig, TimeoutBudgetPlugin  # noqa: E402
from nsgablack.utils.parallel import with_parallel_evaluation  # noqa: E402
from nsgablack.utils.wiring import attach_default_observability_plugins  # noqa: E402
from nsgablack.utils.viz import launch_from_builder  # noqa: E402

from inner_solver import InnerProductionSolverConfig
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
    p.add_argument("--max-moved-events", type=int, default=100, help="Hard cap on moved supply events (<=0 to disable).")
    p.add_argument("--inner-max-calls", type=int, default=500, help="Max nested inner evaluations (<=0 to disable call cap).")
    p.add_argument("--inner-time-budget-ms", type=float, default=0.0, help="Nested inner time budget in ms (<=0 disables time cap).")

    p.add_argument("--pop-size", type=int, default=60)
    p.add_argument("--generations", type=int, default=40)

    p.add_argument("--parallel", action="store_true")
    p.add_argument(
        "--parallel-backend",
        type=str,
        default="thread",
        choices=["thread", "process", "ray", "joblib", "auto", "redis"],
        help="Backward-compatible default backend. Use outer/inner flags to split nested runs.",
    )
    p.add_argument(
        "--outer-parallel-backend",
        type=str,
        default=None,
        choices=["thread", "auto", "redis"],
        help="Outer nested candidate backend. redis submits tasks to L0 worker queue.",
    )
    p.add_argument(
        "--inner-parallel-backend",
        type=str,
        default=None,
        choices=["thread", "process", "ray", "joblib", "auto"],
        help="Inner production solver backend. Redis is intentionally not valid here.",
    )
    p.add_argument("--parallel-workers", type=int, default=8)
    p.add_argument("--outer-parallel-workers", type=int, default=None, help="Outer nested candidate workers; default caps at 4.")
    p.add_argument("--inner-parallel-workers", type=int, default=None, help="Inner production solver workers; default uses --parallel-workers.")
    p.add_argument("--outer-task-threads", type=int, default=1, help="Threads requested by one outer candidate task.")
    p.add_argument("--outer-memory-mb", type=float, default=0.0)
    p.add_argument("--outer-gpus", type=int, default=0)
    p.add_argument("--outer-device-token", action="append", default=[])
    p.add_argument("--outer-gpu-memory-mb", type=float, default=0.0)
    p.add_argument("--inner-memory-mb", type=float, default=0.0)
    p.add_argument("--inner-gpus", type=int, default=0)
    p.add_argument("--inner-device-token", action="append", default=[])
    p.add_argument("--inner-gpu-memory-mb", type=float, default=0.0)
    p.add_argument("--parallel-thread-bias-isolation", type=str, default="off", choices=["off", "disable_cache", "deepcopy"])
    p.add_argument("--parallel-strict", action="store_true")
    p.add_argument("--nested-task-timeout-seconds", type=float, default=0.0, help="Outer nested generation timeout for thread backend (<=0 disables).")
    p.add_argument("--redis-url", type=str, default="redis://localhost:6379/0")
    p.add_argument("--redis-namespace", type=str, default="nsgablack:supply_adjustment_nested")
    p.add_argument("--redis-queue-scope", type=str, default="global", choices=["global", "run"])
    p.add_argument("--redis-timeout-seconds", type=float, default=3600.0)
    p.add_argument("--redis-poll-interval-seconds", type=float, default=1.0)
    p.add_argument("--redis-result-ttl-seconds", type=int, default=86400)

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

    common_backend = str(args.parallel_backend)
    outer_backend = str(args.outer_parallel_backend or common_backend)
    inner_backend = str(args.inner_parallel_backend or ("thread" if common_backend == "redis" else common_backend))
    if inner_backend == "redis":
        raise ValueError("inner production solver cannot use backend='redis'; use --outer-parallel-backend redis instead.")

    base_workers = int(max(1, int(args.parallel_workers)))
    outer_workers = int(args.outer_parallel_workers) if args.outer_parallel_workers is not None else min(4, base_workers)
    inner_workers = int(args.inner_parallel_workers) if args.inner_parallel_workers is not None else base_workers
    outer_workers = max(1, outer_workers)
    inner_workers = max(1, inner_workers)
    outer_task_requirement = _build_resource_requirement(
        threads=int(max(1, int(args.outer_task_threads))),
        gpus=int(args.outer_gpus),
        memory_mb=float(args.outer_memory_mb),
        gpu_memory_mb=float(args.outer_gpu_memory_mb),
        device_tokens=tuple(args.outer_device_token or ()),
        capabilities=("nested_eval",),
        metadata={
            "layer": "L1",
            "role": "outer_candidate_task",
            "executor_backend": str(outer_backend),
            "outer_parallel_workers": int(outer_workers),
        },
    )
    inner_resource_requirement = _build_resource_requirement(
        threads=int(inner_workers),
        gpus=int(args.inner_gpus),
        memory_mb=float(args.inner_memory_mb),
        gpu_memory_mb=float(args.inner_gpu_memory_mb),
        device_tokens=tuple(args.inner_device_token or ()),
        capabilities=("production_inner", "nested_eval"),
        metadata={
            "layer": "L2",
            "role": "inner_production_solver",
            "executor_backend": str(inner_backend),
            "inner_parallel_workers": int(inner_workers),
        },
    )

    inner_cfg = InnerProductionSolverConfig(
        pop_size=int(args.hybrid_refine_pop_size),
        generations=int(args.hybrid_refine_generations),
        max_active_machines_per_day=int(args.max_active_machines),
        max_production_per_machine=float(args.max_production_per_machine),
        parallel=bool(args.parallel),
        parallel_backend=str(inner_backend),
        parallel_workers=int(inner_workers),
        parallel_chunk_size=getattr(args, "parallel_chunk_size", None),
        parallel_strict=bool(args.parallel_strict),
        parallel_thread_bias_isolation=str(args.parallel_thread_bias_isolation),
        resource_requirement=inner_resource_requirement,
    )

    problem = SupplyEventShiftProblem(
        base_supply=np.asarray(data.supply_matrix, dtype=float),
        bom_matrix=np.asarray(data.bom_matrix, dtype=float),
        production_case_dir=(_THIS_DIR.parent / "production_scheduling").resolve(),
        inner_solver_cfg=inner_cfg,
        material_ids=np.arange(1, int(args.materials) + 1),
        max_moved_events=(None if int(args.max_moved_events) <= 0 else int(args.max_moved_events)),
        outer_task_requirement=outer_task_requirement,
        inner_resource_requirement=inner_resource_requirement,
    )

    print(f"[outer] adjustable_events={problem.dimension} materials={problem.materials} days=31")
    print("[window] production_window=day0..30 adjustable_supply_event_day_range=1..30")
    print(
        f"[inner] mode=full_nested "
        f"inner_pop={args.hybrid_refine_pop_size} inner_gen={args.hybrid_refine_generations} "
        f"max_active_machines={args.max_active_machines} max_prod={args.max_production_per_machine} "
        f"max_moved_events={('off' if int(args.max_moved_events) <= 0 else int(args.max_moved_events))}"
    )
    run_id = args.run_id or datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir = Path(args.run_dir)
    run_dir.mkdir(parents=True, exist_ok=True)

    print(
        f"[parallel] enabled={bool(args.parallel)} "
        f"outer_backend={outer_backend} outer_workers={outer_workers} "
        f"inner_backend={inner_backend} inner_workers={inner_workers}"
    )
    print(f"[l0] outer_task_requirement={outer_task_requirement.as_dict()}")
    print(f"[l0] inner_resource_requirement={inner_resource_requirement.as_dict()}")
    if outer_backend == "redis":
        print(
            f"[redis] namespace={args.redis_namespace} scope={args.redis_queue_scope} "
            f"url={args.redis_url} timeout={args.redis_timeout_seconds}s"
        )
    if int(args.max_moved_events) <= 0:
        print("[constraint] max_moved_events=off (no hard cap)")
    else:
        print(f"[constraint] max_moved_events<={int(args.max_moved_events)} (hard cap enabled)")

    nested_extra_context = {}
    nested_timeout = float(getattr(args, "nested_task_timeout_seconds", 0.0))
    if nested_timeout > 0:
        nested_extra_context["task_timeout_seconds"] = nested_timeout
    if outer_backend == "redis":
        nested_extra_context.update(
            {
                "redis_url": str(args.redis_url),
                "namespace": str(args.redis_namespace),
                "queue_scope": str(args.redis_queue_scope),
                "result_ttl_seconds": int(args.redis_result_ttl_seconds),
                "run_id": str(run_id),
                "timeout_seconds": float(args.redis_timeout_seconds),
                "poll_interval_seconds": float(args.redis_poll_interval_seconds),
                "artifact_base_dir": str(run_dir / "l0_artifacts"),
            }
        )

    SolverCls = with_parallel_evaluation(EvolutionSolver)
    solver = SolverCls(
        problem,
        pop_size=int(args.pop_size),
        max_generations=int(args.generations),
        enable_parallel=bool(args.parallel),
        parallel_backend=outer_backend,
        parallel_max_workers=int(outer_workers),
        parallel_thread_bias_isolation=args.parallel_thread_bias_isolation,
        parallel_strict=bool(args.parallel_strict),
        parallel_extra_context=nested_extra_context,
    )
    solver.outer_task_requirement = outer_task_requirement
    solver.outer_resource_requirement = outer_task_requirement
    solver.inner_resource_requirement = inner_resource_requirement
    solver.l0_runtime_summary = {
        "schema": "supply_adjustment_nested.l0_runtime_summary.v1",
        "run_id": str(run_id),
        "outer": {
            "backend": str(outer_backend),
            "parallel_workers": int(outer_workers),
            "task_requirement": outer_task_requirement.as_dict(),
        },
        "inner": {
            "backend": str(inner_backend),
            "parallel_workers": int(inner_workers),
            "resource_requirement": inner_resource_requirement.as_dict(),
        },
        "redis": (
            {
                "url": str(args.redis_url),
                "namespace": str(args.redis_namespace),
                "queue_scope": str(args.redis_queue_scope),
                "timeout_seconds": float(args.redis_timeout_seconds),
                "poll_interval_seconds": float(args.redis_poll_interval_seconds),
                "result_ttl_seconds": int(args.redis_result_ttl_seconds),
            }
            if outer_backend == "redis"
            else None
        ),
    }
    solver.objective_scalarizer = _supply_adjustment_score

    attach_default_observability_plugins(
        solver,
        output_dir=str(run_dir),
        run_id=str(run_id),
        enable_decision_trace=not bool(args.no_decision_trace),
        enable_profiler=not bool(args.no_profiler),
    )
    inner_max_calls = int(getattr(args, "inner_max_calls", 500))
    inner_time_budget_ms = float(getattr(args, "inner_time_budget_ms", 0.0))
    if inner_max_calls > 0 or inner_time_budget_ms > 0:
        solver.add_plugin(
            TimeoutBudgetPlugin(
                config=TimeoutBudgetConfig(
                    layer="L2",
                    max_calls=(inner_max_calls if inner_max_calls > 0 else 1_000_000_000),
                    time_budget_ms=(inner_time_budget_ms if inner_time_budget_ms > 0 else 1.0e12),
                    fail_closed=True,
                )
            )
        )
    problem.inner_runtime_evaluator = TaskInnerRuntimeEvaluator(
        config=InnerRuntimeConfig(source_layer="L2", target_layer="L1")
    )
    solver.add_plugin(SupplyAdjustmentExportPlugin(case_problem=problem, output_dir=run_dir, run_id=run_id))
    return solver


def _supply_adjustment_score(objectives: np.ndarray, violations: np.ndarray, idx: int) -> float:
    obj = np.asarray(objectives, dtype=float)
    if obj.ndim == 1:
        obj = obj.reshape(1, -1)
    row = obj[int(idx)].reshape(-1)
    vio = 0.0
    try:
        vio_arr = np.asarray(violations, dtype=float).reshape(-1)
        if vio_arr.size > int(idx):
            vio = max(0.0, float(vio_arr[int(idx)]))
    except Exception:
        vio = 0.0
    output_term = float(row[0]) if row.size > 0 else 0.0
    moved_events = float(row[1]) if row.size > 1 else 0.0
    moved_days = float(row[2]) if row.size > 2 else 0.0
    return output_term + moved_events + (0.25 * moved_days) + (1_000_000.0 * vio)


def build_solver(argv: Optional[list] = None):
    args = build_parser().parse_args(argv if argv is not None else [])
    return _build_solver_from_args(args)


def _build_resource_requirement(
    *,
    threads: int,
    gpus: int,
    memory_mb: float,
    gpu_memory_mb: float,
    device_tokens: tuple[str, ...],
    capabilities: tuple[str, ...],
    metadata: dict,
) -> ResourceRequirement:
    return ResourceRequirement(
        threads=int(max(1, threads)),
        gpus=int(max(0, gpus)),
        resource_backend="local",
        device_tokens=tuple(str(x) for x in device_tokens if str(x)),
        memory_mb=(float(memory_mb) if float(memory_mb) > 0 else None),
        gpu_memory_mb=(float(gpu_memory_mb) if float(gpu_memory_mb) > 0 else None),
        capabilities=tuple(dict.fromkeys(str(x) for x in capabilities if str(x))),
        metadata=dict(metadata),
    )


def main(argv: Optional[list] = None) -> None:
    args = build_parser().parse_args(argv)
    if bool(args.ui):
        launch_from_builder(lambda: _build_solver_from_args(args), entry_label="solver/assembly.py:build_solver")
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

