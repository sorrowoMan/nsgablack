"""L0 prototype: optimize material blacklist for nested supply adjustment case.
python examples/cases/supply_adjustment_nested/working_blacklist_optimizer.py `
  --no-baseline `
  --max-moved-events 100 `
  --parallel --parallel-backend thread --parallel-workers 12 `
  --parallel-thread-bias-isolation disable_cache `
  --l0-pop-size 8 --l0-generations 6 `
  --l1-pop-size 8 --l1-generations 6 `
  --final-l1-pop-size 12 --final-l1-generations 20

"""

from __future__ import annotations

import argparse
import json
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
from nsgablack.representation.base import RepresentationPipeline  # noqa: E402
from nsgablack.representation.binary import BinaryInitializer, BinaryRepair, BitFlipMutation  # noqa: E402
from nsgablack.utils.suites import attach_default_observability_plugins  # noqa: E402
from nsgablack.utils.viz import launch_from_builder  # noqa: E402

from evaluation import ProductionInnerEvalConfig, ProductionInnerEvaluationModel
from problem import BlacklistDesignProblem, BlacklistEvalConfig
from problem.supply_event_shift_problem import SupplyEventShiftProblem


def _resolve_default_baseline_plan(base_dir: Path) -> Optional[Path]:
    cases_dir = base_dir.parent
    cands = sorted(cases_dir.glob("integrated_result_production_*.xlsx"), reverse=True)
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


def _read_ids_file(path: Path) -> list[int]:
    if not path.exists():
        return []
    out: list[int] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if not s:
            continue
        try:
            out.append(int(s))
        except Exception:
            continue
    return sorted(set(out))


def _read_relational_candidates(path: Path) -> list[int]:
    if not path.exists():
        return []
    obj = json.loads(path.read_text(encoding="utf-8"))
    recs = obj.get("records", [])
    ids = [int(r["material_id"]) for r in recs if bool(r.get("relational_safe", False))]
    return sorted(set(ids))


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="L0 blacklist optimizer for supply-adjustment nested case.")
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--machines", type=int, default=22)
    p.add_argument("--materials", type=int, default=157)
    p.add_argument("--days", type=int, default=31)
    p.add_argument("--bom", type=str, default=None)
    p.add_argument("--supply", type=str, default=None)
    p.add_argument("--baseline-plan", type=str, default=None)
    p.add_argument(
        "--no-baseline",
        action="store_true",
        help="Disable baseline schedule guidance and run pure nested optimization.",
    )

    p.add_argument("--strict-blacklist-file", type=str, default="material_blacklist_strict.txt")
    p.add_argument("--relational-report-file", type=str, default="material_blacklist_relational_report.json")

    p.add_argument("--l0-pop-size", type=int, default=16)
    p.add_argument("--l0-generations", type=int, default=6)
    p.add_argument("--l0-init-prob", type=float, default=0.5)
    p.add_argument("--l0-bitflip-rate", type=float, default=0.06)
    p.add_argument("--l1-pop-size", type=int, default=16)
    p.add_argument("--l1-generations", type=int, default=3)
    p.add_argument("--inner-mode", type=str, default="full", choices=["full", "integrated", "fast", "hybrid"])
    p.add_argument("--final-l1-pop-size", type=int, default=48)
    p.add_argument("--final-l1-generations", type=int, default=12)
    p.add_argument("--quality-gap-soft-limit", type=float, default=0.08)
    p.add_argument("--max-moved-events", type=int, default=200, help="Hard cap on moved supply events (<=0 to disable).")
    p.add_argument("--parallel", action="store_true", help="Enable inner full-solver parallel evaluation.")
    p.add_argument("--parallel-backend", type=str, default="thread", choices=["thread", "process", "ray"])
    p.add_argument("--parallel-workers", type=int, default=8)
    p.add_argument("--parallel-chunk-size", type=int, default=None)
    p.add_argument("--parallel-strict", action="store_true")
    p.add_argument(
        "--parallel-thread-bias-isolation",
        type=str,
        default="off",
        choices=["off", "disable_cache", "deepcopy"],
    )

    p.add_argument("--run-id", type=str, default=None)
    p.add_argument("--run-dir", type=str, default="runs/supply_adjustment_nested")
    p.add_argument("--no-decision-trace", action="store_true")
    p.add_argument("--no-profiler", action="store_true")
    p.add_argument("--ui", action="store_true")
    return p


def _build_solver(args):
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
    print("[window] production_window=day0..30 adjustable_supply_event_day_range=1..30")
    baseline_plan_path = None
    if not bool(getattr(args, "no_baseline", False)):
        baseline_plan_path = (
            Path(args.baseline_plan)
            if getattr(args, "baseline_plan", None)
            else _resolve_default_baseline_plan(_THIS_DIR)
        )
    baseline_schedule = None
    if baseline_plan_path is not None and baseline_plan_path.exists():
        baseline_schedule = _load_baseline_schedule(
            baseline_plan_path,
            machines=int(args.machines),
            days=int(args.days),
        )
        print(f"[data] baseline_plan={baseline_plan_path}")

    strict_ids = _read_ids_file((_THIS_DIR / args.strict_blacklist_file).resolve())
    relational_ids = _read_relational_candidates((_THIS_DIR / args.relational_report_file).resolve())
    candidates = sorted(set(relational_ids).difference(set(strict_ids)))
    print(
        "[l0] initializing "
        f"strict_ids={len(strict_ids)} relational_safe={len(relational_ids)} "
        f"material_candidates={len(candidates)} (building baseline for quality-gap reference)"
    )

    run_id = args.run_id or datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir = Path(args.run_dir)
    run_dir.mkdir(parents=True, exist_ok=True)

    problem = BlacklistDesignProblem(
        base_supply=np.asarray(data.supply_matrix, dtype=float),
        bom_matrix=np.asarray(data.bom_matrix, dtype=float),
        material_ids=np.arange(1, int(args.materials) + 1),
        production_case_dir=(_THIS_DIR.parent / "production_scheduling").resolve(),
        baseline_schedule=baseline_schedule,
        strict_blacklist_ids=strict_ids,
        candidate_material_ids=candidates,
        eval_cfg=BlacklistEvalConfig(
            outer_pop_size=int(args.l1_pop_size),
            outer_generations=int(args.l1_generations),
            inner_mode=str(args.inner_mode),
            quality_gap_soft_limit=float(args.quality_gap_soft_limit),
            max_moved_events=(None if int(args.max_moved_events) <= 0 else int(args.max_moved_events)),
            parallel=bool(args.parallel),
            parallel_backend=str(args.parallel_backend),
            parallel_workers=int(max(1, args.parallel_workers)),
            parallel_chunk_size=args.parallel_chunk_size,
            parallel_strict=bool(args.parallel_strict),
            parallel_thread_bias_isolation=str(args.parallel_thread_bias_isolation),
        ),
        seed=int(args.seed),
    )
    print(
        f"[l0] strict_ids={len(strict_ids)} relational_safe={len(relational_ids)} "
        f"material_candidates={len(candidates)} l0_dim={problem.dimension} inner_mode={args.inner_mode} "
        f"parallel={bool(args.parallel)} backend={args.parallel_backend} workers={int(max(1, args.parallel_workers))} "
        f"max_moved_events={('off' if int(args.max_moved_events) <= 0 else int(args.max_moved_events))}"
    )
    if int(args.max_moved_events) <= 0:
        print("[constraint] max_moved_events=off (no hard cap)")
    else:
        print(f"[constraint] max_moved_events<={int(args.max_moved_events)} (hard cap enabled)")

    solver = EvolutionSolver(
        problem,
        pop_size=int(args.l0_pop_size),
        max_generations=int(args.l0_generations),
    )
    # L0 is binary combinational search: use binary initializer/mutation/repair.
    l0_pipeline = RepresentationPipeline(
        initializer=BinaryInitializer(probability=float(np.clip(args.l0_init_prob, 0.0, 1.0))),
        mutator=BitFlipMutation(rate=float(np.clip(args.l0_bitflip_rate, 0.0, 1.0))),
        repair=BinaryRepair(threshold=0.5),
    )
    solver.set_representation_pipeline(l0_pipeline)
    # Keep crossover conservative in binary space to reduce noisy floating intermediates.
    solver.set_solver_hyperparams(crossover_rate=0.35)
    attach_default_observability_plugins(
        solver,
        output_dir=str(run_dir),
        run_id=str(run_id),
        enable_decision_trace=not bool(args.no_decision_trace),
        enable_profiler=not bool(args.no_profiler),
    )
    # Hook L0 decision events to trace sink when available.
    problem.decision_sink = getattr(solver, "record_decision_event", None)
    solver._l0_run_dir = run_dir  # type: ignore[attr-defined]
    solver._l0_run_id = run_id  # type: ignore[attr-defined]
    return solver


def _dump_best_blacklist(solver) -> None:
    problem = getattr(solver, "problem", None)
    x = getattr(solver, "best_x", None)
    if x is None:
        try:
            pop = np.asarray(getattr(solver, "population", None), dtype=float)
            obj = np.asarray(getattr(solver, "objectives", None), dtype=float)
            if pop.ndim == 2 and pop.shape[0] > 0:
                if obj.ndim == 2 and obj.shape[0] == pop.shape[0]:
                    score = np.sum(obj - np.min(obj, axis=0, keepdims=True), axis=1)
                    x = pop[int(np.argmin(score))]
                else:
                    x = pop[0]
        except Exception:
            x = None
    if problem is None or x is None:
        return
    try:
        ids = problem._decode_blacklist_ids(np.asarray(x, dtype=float))
    except Exception:
        return
    run_dir = getattr(solver, "_l0_run_dir", Path("runs/supply_adjustment_nested"))
    run_id = getattr(solver, "_l0_run_id", datetime.now().strftime("%Y%m%d_%H%M%S"))
    out = Path(run_dir) / f"best_blacklist_{run_id}.json"
    payload = {
        "count": int(len(ids)),
        "material_ids": [int(x) for x in ids],
        "best_objective": getattr(solver, "best_objective", None),
    }
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[l0] best_blacklist={out} count={len(ids)}")


def _export_supply_like_xlsx(*, adjusted_supply: np.ndarray, material_ids: np.ndarray, out_xlsx: Path) -> None:
    import pandas as pd

    supply = np.asarray(adjusted_supply, dtype=float)
    m, d = supply.shape
    mat = np.asarray(material_ids).reshape(m)
    cols = {"物料": mat.tolist()}
    for day in range(d):
        cols[day] = supply[:, day].astype(float).tolist()
    df = pd.DataFrame(cols)
    out_xlsx.parent.mkdir(parents=True, exist_ok=True)
    df.to_excel(out_xlsx, index=False, sheet_name="adjusted_supply")


def _run_final_l1_and_export(*, solver, args) -> None:
    problem_l0 = getattr(solver, "problem", None)
    x = getattr(solver, "best_x", None)
    if problem_l0 is None:
        return
    if x is None:
        try:
            pop = np.asarray(getattr(solver, "population", None), dtype=float)
            if pop.ndim == 2 and pop.shape[0] > 0:
                x = pop[0]
        except Exception:
            x = None
    if x is None:
        return

    blacklist_ids = problem_l0._decode_blacklist_ids(np.asarray(x, dtype=float))
    base_supply = np.asarray(problem_l0.base_supply, dtype=float)
    bom_matrix = np.asarray(problem_l0.bom_matrix, dtype=float)
    baseline_schedule = getattr(problem_l0, "baseline_schedule", None)
    production_case_dir = getattr(problem_l0, "production_case_dir", _THIS_DIR.parent / "production_scheduling")
    material_ids = np.asarray(problem_l0.material_ids)

    inner = ProductionInnerEvaluationModel(
        bom_matrix=bom_matrix,
        base_supply=base_supply,
        production_case_dir=Path(production_case_dir),
        baseline_schedule=baseline_schedule,
        cfg=ProductionInnerEvalConfig(
            mode=str(args.inner_mode),
            inner_trials=2,
            hybrid_top_quantile=0.85,
            hybrid_explore_prob=0.02,
            hybrid_random_refine_ratio=0.10,
            hybrid_warmup=12,
            hybrid_refine_pop_size=max(8, int(args.final_l1_pop_size // 2)),
            hybrid_refine_generations=max(1, int(args.final_l1_generations // 4)),
            parallel=bool(args.parallel),
            parallel_backend=str(args.parallel_backend),
            parallel_workers=int(max(1, args.parallel_workers)),
            parallel_chunk_size=args.parallel_chunk_size,
            parallel_strict=bool(args.parallel_strict),
            parallel_thread_bias_isolation=str(args.parallel_thread_bias_isolation),
        ),
    )
    p = SupplyEventShiftProblem(
        base_supply=base_supply,
        inner_model=inner,
        material_ids=material_ids,
        material_blacklist=blacklist_ids,
        max_moved_events=(None if int(args.max_moved_events) <= 0 else int(args.max_moved_events)),
    )
    s = EvolutionSolver(
        p,
        pop_size=int(max(4, args.final_l1_pop_size)),
        max_generations=int(max(1, args.final_l1_generations)),
    )
    s.run()
    best_x = getattr(s, "best_x", None)
    if best_x is None:
        try:
            pop = np.asarray(getattr(s, "population", None), dtype=float)
            obj = np.asarray(getattr(s, "objectives", None), dtype=float)
            if pop.ndim == 2 and pop.shape[0] > 0:
                if obj.ndim == 2 and obj.shape[0] == pop.shape[0]:
                    idx = int(np.argmin(np.sum(obj, axis=1)))
                else:
                    idx = 0
                best_x = pop[idx]
        except Exception:
            best_x = None
    if best_x is None:
        return
    shifts = p.decode_shifts(np.asarray(best_x, dtype=float))
    adjusted_supply = p.apply_shifts(shifts)
    moved_events = int(np.sum(shifts > 0))
    moved_days = int(np.sum(shifts))

    run_dir = Path(getattr(solver, "_l0_run_dir", Path("runs/supply_adjustment_nested")))
    run_id = str(getattr(solver, "_l0_run_id", datetime.now().strftime("%Y%m%d_%H%M%S")))
    out_xlsx = run_dir / f"SUPPLY_adjusted_from_l1_{run_id}.xlsx"
    out_csv = run_dir / f"SUPPLY_adjusted_moves_{run_id}.csv"
    _export_supply_like_xlsx(adjusted_supply=adjusted_supply, material_ids=material_ids, out_xlsx=out_xlsx)
    p.export_move_log(shifts, out_csv)
    print(f"[l1] export_supply={out_xlsx}")
    print(f"[l1] export_moves={out_csv}")
    print(f"[l1] moved_events={moved_events} moved_days={moved_days}")


def build_solver(argv: Optional[list] = None):
    args = build_parser().parse_args(argv if argv is not None else [])
    return _build_solver(args)


def main(argv: Optional[list] = None) -> None:
    args = build_parser().parse_args(argv)
    if bool(args.ui):
        launch_from_builder(lambda: _build_solver(args), entry_label="working_blacklist_optimizer.py:build_solver")
        return
    solver = _build_solver(args)
    result = solver.run()
    _dump_best_blacklist(solver)
    _run_final_l1_and_export(solver=solver, args=args)
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
