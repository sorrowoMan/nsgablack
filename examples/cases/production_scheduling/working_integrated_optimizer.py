# -*- coding: utf-8 -*-
"""Refactored entrypoint: pipeline-first production scheduling.

This script is a real-world application of NSGABlack's decomposition:
- Problem: `ProductionSchedulingProblem.evaluate(x)` defines objectives.
- RepresentationPipeline: initializer/mutator/repair enforce feasibility.
- BiasModule: soft preferences and engineering guidance (optional).
- Solver/Adapter: choose either the stable NSGA-II base, or a composable
  multi-strategy controller ("multi-agent" as cooperating strategies).
"""

from __future__ import annotations

import argparse
import os
import random
import sys
import time
from pathlib import Path
from datetime import datetime
from typing import Optional

import numpy as np


# Ensure local helper import works when executed as a script.
_THIS_DIR = Path(__file__).resolve().parent
if str(_THIS_DIR) not in sys.path:
    sys.path.insert(0, str(_THIS_DIR))

from _bootstrap import ensure_nsgablack_importable  # noqa: E402

ensure_nsgablack_importable(Path(__file__))

from nsgablack.core.composable_solver import ComposableSolver  # noqa: E402
from nsgablack.core.adapters import (  # noqa: E402
    AlgorithmAdapter,
    MultiStrategyConfig,
    MultiStrategyControllerAdapter,
    RoleSpec,
)
from nsgablack.plugins import (  # noqa: E402
    ParetoArchivePlugin,
    BenchmarkHarnessPlugin,
    BenchmarkHarnessConfig,
    ModuleReportPlugin,
    ModuleReportConfig,
    ProfilerPlugin,
    ProfilerConfig,
)
from nsgablack.utils.parallel import with_parallel_evaluation  # noqa: E402
from nsgablack.utils.viz import launch_from_builder  # noqa: E402

from refactor_bias import build_production_bias_module
from refactor_data import load_production_data
from refactor_pipeline import build_schedule_pipeline
from refactor_problem import ProductionConstraints, ProductionSchedulingProblem


_PROBLEM_FACTORY_CACHE = {}


class ProductionProblemFactory:
    """
    Picklable factory for multiprocessing parallel evaluation.

    ParallelEvaluator will call `problem_factory()` per task for process backend.
    To avoid re-loading data repeatedly, we cache the constructed problem inside
    each worker process.
    """

    def __init__(
        self,
        *,
        base_dir: str,
        bom: Optional[str],
        supply: Optional[str],
        machines: int,
        materials: int,
        days: int,
        max_machines: int,
        min_machines: int,
        min_prod: int,
        max_prod: int,
        shortage_unit_penalty: float,
        penalty_objective: bool,
        penalty_scale: float,
    ) -> None:
        self.base_dir = str(base_dir)
        self.bom = bom
        self.supply = supply
        self.machines = int(machines)
        self.materials = int(materials)
        self.days = int(days)
        self.max_machines = int(max_machines)
        self.min_machines = int(min_machines)
        self.min_prod = int(min_prod)
        self.max_prod = int(max_prod)
        self.shortage_unit_penalty = float(shortage_unit_penalty)
        self.penalty_objective = bool(penalty_objective)
        self.penalty_scale = float(penalty_scale)

        self._cache_key = (
            self.base_dir,
            self.bom,
            self.supply,
            self.machines,
            self.materials,
            self.days,
            self.max_machines,
            self.min_machines,
            self.min_prod,
            self.max_prod,
            self.shortage_unit_penalty,
            self.penalty_objective,
            self.penalty_scale,
        )

    def __call__(self) -> ProductionSchedulingProblem:
        cached = _PROBLEM_FACTORY_CACHE.get(self._cache_key)
        if cached is not None:
            return cached

        base_dir = Path(self.base_dir)
        data = load_production_data(
            base_dir=base_dir,
            bom_path=Path(self.bom) if self.bom else None,
            supply_path=Path(self.supply) if self.supply else None,
            machines=self.machines,
            materials=self.materials,
            days=self.days,
            fallback=True,
        )
        constraints = ProductionConstraints(
            max_machines_per_day=self.max_machines,
            min_machines_per_day=self.min_machines,
            min_production_per_machine=self.min_prod,
            max_production_per_machine=self.max_prod,
            shortage_unit_penalty=self.shortage_unit_penalty,
            include_penalty_objective=self.penalty_objective,
            penalty_objective_scale=self.penalty_scale,
        )
        problem = ProductionSchedulingProblem(data=data, constraints=constraints)
        _PROBLEM_FACTORY_CACHE[self._cache_key] = problem
        return problem


def _build_problem_factory(args) -> ProductionProblemFactory:
    return ProductionProblemFactory(
        base_dir=str(Path(__file__).resolve().parent),
        bom=args.bom,
        supply=args.supply,
        machines=args.machines,
        materials=args.materials,
        days=args.days,
        max_machines=args.max_machines,
        min_machines=args.min_machines,
        min_prod=args.min_prod,
        max_prod=args.max_prod,
        shortage_unit_penalty=args.shortage_unit_penalty,
        penalty_objective=args.penalty_objective,
        penalty_scale=args.penalty_scale,
    )


class ConsoleProgressPlugin:
    """Minimal console progress to avoid the 'looks stuck' feeling."""

    def __init__(self, report_every: int = 10):
        from nsgablack.plugins import Plugin

        # Use Plugin base to integrate with PluginManager.
        class _Impl(Plugin):
            def __init__(self, report_every: int):
                super().__init__(name="console_progress")
                self.report_every = int(max(1, report_every))
                self._t0 = None
                self._last_t = None

            def on_solver_init(self, solver):
                self._t0 = time.time()
                self._last_t = self._t0

            def on_generation_end(self, generation: int):
                if generation % self.report_every != 0:
                    return
                solver = getattr(self, "solver", None)
                if solver is None:
                    return
                now = time.time()
                dt = (now - self._last_t) if self._last_t is not None else 0.0
                self._last_t = now
                best = getattr(solver, "best_objective", None)
                n = None
                try:
                    n = int(getattr(solver, "last_step_summary", {}).get("num_candidates"))
                except Exception:
                    n = None
                elapsed = (now - self._t0) if self._t0 is not None else 0.0
                if best is None:
                    print(f"[step {generation:04d}] elapsed={elapsed:8.1f}s  last_step={dt:6.2f}s  candidates={n}")
                else:
                    print(
                        f"[step {generation:04d}] elapsed={elapsed:8.1f}s  last_step={dt:6.2f}s  "
                        f"candidates={n}  best_score={best:.6g}"
                    )

        self._plugin = _Impl(report_every=report_every)

    def __getattr__(self, name):
        return getattr(self._plugin, name)


def _build_problem(args) -> ProductionSchedulingProblem:
    data = load_production_data(
        base_dir=Path(__file__).resolve().parent,
        bom_path=Path(args.bom) if args.bom else None,
        supply_path=Path(args.supply) if args.supply else None,
        machines=args.machines,
        materials=args.materials,
        days=args.days,
        fallback=True,
    )
    if getattr(data, "bom_path", None) is not None:
        print(f"[data] bom={data.bom_path}")
    if getattr(data, "supply_path", None) is not None:
        print(f"[data] supply={data.supply_path}")
    constraints = ProductionConstraints(
        max_machines_per_day=args.max_machines,
        min_machines_per_day=args.min_machines,
        min_production_per_machine=args.min_prod,
        max_production_per_machine=args.max_prod,
        shortage_unit_penalty=args.shortage_unit_penalty,
        include_penalty_objective=args.penalty_objective,
        penalty_objective_scale=args.penalty_scale,
    )
    problem = ProductionSchedulingProblem(data=data, constraints=constraints)
    return problem


def _choose_pareto_solutions(problem, individuals: np.ndarray, objectives: np.ndarray):
    if individuals is None or len(individuals) == 0:
        return []
    penalties = []
    for ind in individuals:
        schedule = problem.decode_schedule(ind)
        penalties.append(problem._compute_penalty(schedule))
    penalties = np.asarray(penalties, dtype=float)

    idx_penalty = int(np.argmin(penalties))
    idx_prod = int(np.argmin(objectives[:, 0]))
    picks = []
    seen = set()
    for label, idx in (("penalty", idx_penalty), ("production", idx_prod)):
        if idx in seen:
            continue
        seen.add(idx)
        picks.append((label, individuals[idx], objectives[idx]))
    return picks


def _crowding_distance(objectives: np.ndarray) -> np.ndarray:
    if objectives is None or len(objectives) == 0:
        return np.array([], dtype=float)
    n, m = objectives.shape
    distance = np.zeros(n, dtype=float)
    for obj_idx in range(m):
        order = np.argsort(objectives[:, obj_idx])
        distance[order[0]] = np.inf
        distance[order[-1]] = np.inf
        f_min = objectives[order[0], obj_idx]
        f_max = objectives[order[-1], obj_idx]
        if f_max - f_min <= 1e-12:
            continue
        for i in range(1, n - 1):
            prev_val = objectives[order[i - 1], obj_idx]
            next_val = objectives[order[i + 1], obj_idx]
            distance[order[i]] += (next_val - prev_val) / (f_max - f_min)
    return distance


def _resolve_pareto_export_root(base: Optional[Path]) -> Path:
    if base is None:
        base_dir = Path(__file__).resolve().parents[1]
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        root = base_dir / f"�����Ż����_pareto_{ts}"
    elif base.suffix:
        root = base.with_name(f"{base.stem}_pareto")
    else:
        root = base
    root.mkdir(parents=True, exist_ok=True)
    return root


def _resolve_summary_path(root: Path) -> Path:
    return root / "pareto_summary.csv"


def _export_pareto_batch(
    problem,
    individuals: np.ndarray,
    objectives: np.ndarray,
    base_export: Optional[Path],
    mode: str,
    limit: int,
) -> int:
    if individuals is None or len(individuals) == 0:
        return 0
    total = len(individuals)
    if limit <= 0:
        limit = total
    else:
        limit = max(1, min(int(limit), total))

    export_root = _resolve_pareto_export_root(base_export)
    ext = ".xlsx"
    if base_export is not None and base_export.suffix:
        ext = base_export.suffix

    if mode == "crowding":
        crowd = _crowding_distance(objectives)
        order = np.argsort(-crowd)
    elif mode == "production":
        order = np.argsort(objectives[:, 0])
    else:
        order = np.arange(total)

    selected = order[:limit]
    rows = []
    for rank, idx in enumerate(selected, start=1):
        label = f"pareto{rank:02d}"
        schedule = problem.decode_schedule(individuals[idx])
        summary = problem.summarize_schedule(schedule)
        export_path = export_root / f"{label}{ext}"
        _export_schedule(export_path, schedule)
        row = {"label": label, "file": str(export_path)}
        for j, value in enumerate(objectives[idx]):
            row[f"obj{j}"] = float(value)
        row.update(summary)
        rows.append(row)

    if rows:
        import pandas as pd

        summary_path = _resolve_summary_path(export_root)
        df = pd.DataFrame(rows)
        df.to_csv(summary_path, index=False)
    return len(rows)


def _default_export_path(prefix: str = "�����Ż����", label: Optional[str] = None) -> Path:
    base_dir = Path(__file__).resolve().parents[1]
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    if label:
        return base_dir / f"{prefix}_{label}_{ts}.xlsx"
    return base_dir / f"{prefix}_{ts}.xlsx"


def _resolve_export_path(base: Optional[Path], label: str) -> Path:
    if base is None:
        return _default_export_path(label=label)
    if base.suffix:
        return base.with_name(f"{base.stem}_{label}{base.suffix}")
    return base / _default_export_path(label=label).name


def _export_schedule(path: Path, schedule: np.ndarray) -> None:
    import pandas as pd

    schedule = np.asarray(schedule, dtype=float)
    schedule = np.clip(np.floor(schedule), 0, None).astype(int)
    machines, days = schedule.shape

    data = {
        "Day_Index": list(range(days)),
        "Date": [f"�滮��{day}" for day in range(days)],
    }
    for m in range(machines):
        data[f"����{m}"] = schedule[m, :].tolist()

    df = pd.DataFrame(data)
    if path.suffix.lower() == ".xlsx":
        # Keep a stable sheet name for downstream visualization scripts.
        df.to_excel(path, index=False, sheet_name="�����ƻ�")
    else:
        df.to_csv(path, index=False)


def _extract_pareto(solver_or_result) -> tuple[Optional[np.ndarray], Optional[np.ndarray]]:
    """
    Normalize Pareto outputs from either:
    - BlackBoxSolverNSGAII result dict
    - ComposableSolver + ParetoArchivePlugin (solver.pareto_*)
    """
    if isinstance(solver_or_result, dict):
        pareto = solver_or_result.get("pareto_solutions")
        if isinstance(pareto, dict) and "individuals" in pareto:
            individuals = np.asarray(pareto["individuals"], dtype=float)
            objectives = np.asarray(pareto["objectives"], dtype=float)
            return individuals, objectives
        return None, None

    pareto_X = getattr(solver_or_result, "pareto_solutions", None)
    pareto_F = getattr(solver_or_result, "pareto_objectives", None)
    if pareto_X is None or pareto_F is None:
        return None, None
    return np.asarray(pareto_X, dtype=float), np.asarray(pareto_F, dtype=float)


class ProductionRandomSearchAdapter(AlgorithmAdapter):
    """Explorer: generate diverse feasible candidates via init+repair."""

    def __init__(self, *, batch_size: int = 32):
        super().__init__(name="production_random_search")
        self.batch_size = int(batch_size)

    def propose(self, solver, context):
        out = []
        for _ in range(max(1, self.batch_size)):
            x = solver.init_candidate(context)
            x = solver.repair_candidate(x, context)
            out.append(x)
        return out


class ProductionLocalSearchAdapter(AlgorithmAdapter):
    """Exploiter: refine best solution via mutate+repair."""

    def __init__(self, *, batch_size: int = 16):
        super().__init__(name="production_local_search")
        self.batch_size = int(batch_size)

    def propose(self, solver, context):
        base = solver.best_x
        out = []
        for _ in range(max(1, self.batch_size)):
            if base is None:
                x = solver.init_candidate(context)
            else:
                x = solver.mutate_candidate(base, context)
            x = solver.repair_candidate(x, context)
            out.append(x)
        return out


def run_nsga2(problem, args):
    raise RuntimeError(
        "nsga2 path has been removed from this application entrypoint. "
        "Use `--solver multi-agent` (default) for cooperative search."
    )


def build_multi_agent_solver(problem, args):
    """Build solver for multi-agent cooperation (no run)."""
    pipeline = build_schedule_pipeline(
        problem,
        problem.constraints,
        material_cap_ratio=args.material_cap_ratio,
        daily_floor_ratio=args.daily_floor_ratio,
        donor_keep_ratio=args.donor_keep_ratio,
        daily_cap_ratio=args.daily_cap_ratio,
        reserve_ratio=args.reserve_ratio,
        coverage_bonus=args.coverage_bonus,
        budget_mode=args.budget_mode,
        smooth_strength=args.smooth_strength,
        smooth_passes=args.smooth_passes,
    )
    if bool(getattr(args, "no_pipeline", False)):
        # Keep initializer+mutator, but bypass all repair/smoothing so users can do ablation.
        pipeline.repair = None
    bias_module = (
        None
        if args.no_bias
        else build_production_bias_module(
            problem,
            weights={
                "coverage_reward": args.coverage_reward,
                "smoothness_penalty": args.smoothness_penalty,
                "variance_penalty": args.variance_penalty,
            },
        )
    )

    total_batch = max(8, int(args.pop_size))
    explorer_batch = max(4, int(total_batch * 0.65))
    exploiter_batch = max(4, total_batch - explorer_batch)

    roles = [
        RoleSpec(
            name="explorer",
            adapter=lambda uid: ProductionRandomSearchAdapter(batch_size=max(4, explorer_batch // 4)),
            n_units=4,
            weight=1.0,
        ),
        RoleSpec(
            name="exploiter",
            adapter=lambda uid: ProductionLocalSearchAdapter(batch_size=max(2, exploiter_batch // 2)),
            n_units=2,
            weight=1.0,
        ),
    ]

    cfg = MultiStrategyConfig(
        total_batch_size=total_batch,
        objective_aggregation="sum",
        adapt_weights=True,
        stagnation_window=max(5, int(args.adapt_interval)),
        enable_regions=False,
        region_update_interval=max(0, int(args.comm_interval)),
        phase_schedule=(("explore", max(5, int(args.generations // 3))), ("exploit", -1)),
        phase_roles={"explore": ["explorer"], "exploit": ["exploiter"]},
    )

    controller = MultiStrategyControllerAdapter(roles=roles, config=cfg)

    SolverClass = with_parallel_evaluation(ComposableSolver)
    factory = (
        _build_problem_factory(args)
        if args.parallel and args.parallel_backend in ("process", "ray")
        else None
    )
    solver = SolverClass(
        problem=problem,
        adapter=controller,
        representation_pipeline=pipeline,
        bias_module=bias_module,
        enable_parallel=bool(args.parallel),
        parallel_backend=args.parallel_backend,
        parallel_max_workers=args.parallel_workers,
        parallel_chunk_size=args.parallel_chunk_size,
        parallel_verbose=bool(args.parallel_verbose),
        parallel_precheck=not bool(args.parallel_no_precheck),
        parallel_strict=bool(args.parallel_strict),
        parallel_problem_factory=factory,
    )
    if not bool(getattr(args, "no_run_logs", False)):
        repo_root = Path(__file__).resolve().parents[1]
        run_dir = Path(args.run_dir) if getattr(args, "run_dir", None) else (repo_root / "runs" / "production_schedule")
        run_id = str(args.run_id) if getattr(args, "run_id", None) else datetime.now().strftime("%Y%m%d_%H%M%S")
        run_dir = run_dir.expanduser().resolve()
        run_dir.mkdir(parents=True, exist_ok=True)
        solver.add_plugin(
            BenchmarkHarnessPlugin(
                config=BenchmarkHarnessConfig(
                    output_dir=str(run_dir),
                    run_id=str(run_id),
                    seed=None if args.seed is None else int(args.seed),
                    log_every=int(getattr(args, "log_every", 1) or 1),
                    flush_every=10,
                    overwrite=True,
                )
            )
        )
        solver.add_plugin(
            ModuleReportPlugin(
                config=ModuleReportConfig(
                    output_dir=str(run_dir),
                    run_id=str(run_id),
                    write_bias_markdown=not bool(getattr(args, "no_bias_md", False)),
                )
            )
        )
        if not bool(getattr(args, "no_profile", False)):
            solver.add_plugin(
                ProfilerPlugin(
                    config=ProfilerConfig(
                        output_dir=str(run_dir),
                        run_id=str(run_id),
                        overwrite=True,
                        flush_every=0,
                    )
                )
            )
        print(f"[run] logs_dir={run_dir} run_id={run_id}")
    solver.add_plugin(ParetoArchivePlugin())
    solver.add_plugin(ConsoleProgressPlugin(report_every=args.report_every))
    solver.max_steps = int(args.generations)
    return solver


def run_multi_agent(problem, args):
    """
    \"multi-agent\" in this repo is implemented as \"multi-strategy cooperation\":
    multiple strategy adapters propose candidates in parallel, while the solver
    evaluates them together.
    """
    solver = build_multi_agent_solver(problem, args)
    solver.run()

    individuals, objectives = _extract_pareto(solver)
    print(f"Pareto size: {0 if individuals is None else len(individuals)}")
    choices = _choose_pareto_solutions(problem, individuals, objectives) if individuals is not None else []
    if choices and (not bool(getattr(args, "no_export", False))):
        base_export = Path(args.export) if args.export else None
        for label, chosen, obj in choices:
            schedule = problem.decode_schedule(chosen)
            summary = problem.summarize_schedule(schedule)
            print(f"Best ({'lowest penalty' if label == 'penalty' else 'highest production'}):")
            print(f"  objectives: {obj}")
            for key, value in summary.items():
                print(f"  {key}: {value:.4f}")
            export_path = _resolve_export_path(base_export, label)
            _export_schedule(export_path, schedule)
            print(f"Saved schedule to: {export_path}")

    if (not bool(getattr(args, "no_export", False))) and args.pareto_export != 0 and individuals is not None:
        base_export = Path(args.export) if args.export else None
        exported = _export_pareto_batch(
            problem,
            individuals,
            objectives,
            base_export,
            mode=args.pareto_export_mode,
            limit=args.pareto_export,
        )
        if exported:
            print(f"Exported {exported} Pareto schedules.")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Refactored production scheduling (pipeline-first).")
    parser.add_argument("--solver", choices=["multi-agent"], default="multi-agent")
    parser.add_argument("--ui", action="store_true", help="Launch Run Inspector UI before running.")
    parser.add_argument("--bom", type=str, default=None)
    parser.add_argument("--supply", type=str, default=None)
    parser.add_argument("--machines", type=int, default=22)
    parser.add_argument("--materials", type=int, default=156)
    parser.add_argument("--days", type=int, default=31)
    parser.add_argument("--max-machines", type=int, default=8)
    parser.add_argument("--min-machines", type=int, default=5)
    parser.add_argument("--min-prod", type=int, default=50)
    parser.add_argument("--max-prod", type=int, default=3000)
    parser.add_argument("--shortage-unit-penalty", type=float, default=1.0)
    parser.add_argument(
        "--penalty-objective",
        action="store_true",
        help="Include scaled penalty as an objective (default: constraint-only).",
    )
    parser.add_argument(
        "--penalty-scale",
        type=float,
        default=0.001,
        help="Scale for penalty objective when enabled.",
    )
    parser.add_argument("--pop-size", type=int, default=200)
    parser.add_argument("--generations", type=int, default=50)
    parser.add_argument("--crossover-rate", type=float, default=0.85)
    parser.add_argument("--mutation-rate", type=float, default=0.15)
    parser.add_argument("--report-every", type=int, default=10)
    parser.add_argument("--run-dir", type=str, default=None, help="Auto logs dir for benchmark/module reports.")
    parser.add_argument("--run-id", type=str, default=None, help="Run id for reports (default: timestamp).")
    parser.add_argument("--log-every", type=int, default=1, help="BenchmarkHarness CSV log frequency.")
    parser.add_argument("--no-bias-md", action="store_true", help="Disable writing bias.md in module report.")
    parser.add_argument("--no-run-logs", action="store_true", help="Disable automatic benchmark/module reports.")
    parser.add_argument("--no-profile", action="store_true", help="Disable ProfilerPlugin output in run logs.")
    parser.add_argument("--no-export", action="store_true", help="Disable exporting schedules (no Excel/CSV output).")
    parser.add_argument("--comm-interval", type=int, default=5)
    parser.add_argument("--adapt-interval", type=int, default=20)
    parser.add_argument("--parallel", action="store_true", help="Enable parallel evaluation (CPU).")
    parser.add_argument(
        "--parallel-backend",
        choices=["auto", "process", "thread", "joblib", "ray"],
        default="process",
        help="Parallel backend (process recommended for heavy Python evaluation; ray is optional).",
    )
    parser.add_argument("--parallel-workers", type=int, default=None, help="Parallel worker count (default: auto).")
    parser.add_argument("--parallel-chunk-size", type=int, default=None, help="Task chunk size (default: auto).")
    parser.add_argument("--parallel-verbose", action="store_true", help="Verbose parallel evaluator logging.")
    parser.add_argument(
        "--parallel-no-precheck",
        action="store_true",
        help="Disable picklability precheck/fallback for process backend.",
    )
    parser.add_argument("--parallel-strict", action="store_true", help="Strict mode: do not fallback on parallel errors.")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--no-bias", action="store_true")
    parser.add_argument(
        "--no-pipeline",
        action="store_true",
        help="Ablation: keep initializer+mutator, but disable repair/smoothing in the pipeline.",
    )
    parser.add_argument(
        "--material-cap-ratio",
        type=float,
        default=2.0,
        help="Daily material usage cap vs. average allocation (higher = higher output).",
    )
    parser.add_argument(
        "--daily-floor-ratio",
        type=float,
        default=0.55,
        help="Daily production floor vs. average allocation (higher = more stable output).",
    )
    parser.add_argument(
        "--donor-keep-ratio",
        type=float,
        default=0.7,
        help="Minimum fraction of a donor day's total kept during backfill.",
    )
    parser.add_argument(
        "--daily-cap-ratio",
        type=float,
        default=2.2,
        help="Daily production cap vs. average allocation (higher = higher output).",
    )
    parser.add_argument(
        "--budget-mode",
        choices=["average", "today"],
        default="today",
        help="Daily material budget mode (average = capped by remaining days, today = use current stock).",
    )
    parser.add_argument(
        "--smooth-strength",
        type=float,
        default=0.6,
        help="Forward smoothing strength for daily totals (0 = off).",
    )
    parser.add_argument(
        "--smooth-passes",
        type=int,
        default=2,
        help="Number of forward smoothing passes.",
    )
    parser.add_argument(
        "--reserve-ratio",
        type=float,
        default=0.6,
        help="Reserve ratio for next-day continuity (lower = higher output).",
    )
    parser.add_argument(
        "--pareto-export",
        type=int,
        default=-1,
        help="Export N Pareto schedules (-1 = all, 0 = off).",
    )
    parser.add_argument(
        "--pareto-export-mode",
        choices=["front", "crowding", "production"],
        default="crowding",
        help="How to pick Pareto schedules to export.",
    )
    parser.add_argument(
        "--coverage-bonus",
        type=float,
        default=300.0,
        help="Priority bonus for machines never produced yet (higher = richer coverage).",
    )
    parser.add_argument(
        "--coverage-reward",
        type=float,
        default=0.03,
        help="Bias reward for machine coverage ratio (higher = richer coverage).",
    )
    parser.add_argument(
        "--smoothness-penalty",
        type=float,
        default=0.01,
        help="Bias penalty weight for day-to-day changes (higher = smoother daily totals).",
    )
    parser.add_argument(
        "--variance-penalty",
        type=float,
        default=0.03,
        help="Bias penalty weight for daily production variance (higher = more stable daily totals).",
    )
    parser.add_argument(
        "--export",
        type=str,
        default=None,
        help="Save selected schedules; suffixes _penalty/_production will be appended.",
    )
    return parser



def _build_solver_from_args(args) -> ComposableSolver:
    problem = _build_problem(args)
    return build_multi_agent_solver(problem, args)



def build_solver(argv: Optional[list] = None) -> ComposableSolver:
    """
    Build solver for Run Inspector / programmatic launch.

    Usage:
        python -m nsgablack run_inspector --entry working_integrated_optimizer.py:build_solver
    """
    parser = build_parser()
    args = parser.parse_args(argv if argv is not None else [])
    if not getattr(args, "run_id", None):
        args.run_id = datetime.now().strftime("%Y%m%d_%H%M%S")

    random.seed(args.seed)
    np.random.seed(args.seed)

    return _build_solver_from_args(args)


def main(args=None):
    if args is None:
        args = build_parser().parse_args()
    # Defaults: this workload is evaluation-heavy (Python loops + constraints),
    # so parallel evaluation is almost always beneficial on a high-core CPU.
    if not getattr(args, "parallel", False):
        args.parallel = True
    if not getattr(args, "parallel_backend", None):
        args.parallel_backend = "process"
    if getattr(args, "parallel_backend", None) in ("process", "ray") and getattr(args, "parallel_workers", None) is None:
        cpu = int(os.cpu_count() or 8)
        # Leave some cores for OS / IO; cap to avoid excessive memory pressure.
        args.parallel_workers = max(4, min(cpu - 2, 12))

    print(
        "[run] solver=multi-agent "
        f"parallel={bool(args.parallel)} backend={args.parallel_backend} workers={args.parallel_workers} "
        f"generations={args.generations} pop_size={args.pop_size}"
    )
    if bool(args.parallel) and args.parallel_backend == "process":
        print("[run] Note: first parallel step may be slow on Windows due to process spawn + warmup.")
    if bool(args.parallel) and args.parallel_backend == "ray":
        print("[run] Note: ray backend requires `pip install ray`; it will start a local runtime if not already running.")

    random.seed(args.seed)
    np.random.seed(args.seed)

    problem = _build_problem(args)
    run_multi_agent(problem, args)


if __name__ == "__main__":
    args = build_parser().parse_args()
    if args.ui:
        if not getattr(args, "run_id", None):
            args.run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        launch_from_builder(
            lambda: _build_solver_from_args(args),
            entry_label="working_integrated_optimizer.py:build_solver",
        )
        raise SystemExit(0)
    main(args)

