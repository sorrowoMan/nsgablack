# -*- coding: utf-8 -*-
"""Refactored entrypoint: pipeline-first production scheduling.

This script is a real-world application of NSGABlack's decomposition:
- Problem: `ProductionSchedulingProblem.evaluate(x)` defines objectives.
- RepresentationPipeline: initializer/mutator/repair enforce feasibility.
- BiasModule: soft preferences and engineering guidance (optional).
- Solver/Adapter: choose either the stable NSGA-II base, or a composable
  multi-strategy controller ("multi-agent" as cooperating strategies).


  
python examples/cases/production_scheduling/working_integrated_optimizer.py `
  --parallel --parallel-backend thread --parallel-workers 12 `
  --parallel-thread-bias-isolation disable_cache  

"""

from __future__ import annotations

import argparse
import json
import os
import random
import re
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
from nsgablack.adapters import (  # noqa: E402
    AlgorithmAdapter,
    MOEADAdapter,
    MOEADConfig,
    MultiStrategyConfig,
    MultiStrategyControllerAdapter,
    RoleSpec,
    VNSAdapter,
    VNSConfig,
)
from nsgablack.plugins import ParetoArchivePlugin  # noqa: E402
from nsgablack.utils.suites import attach_default_observability_plugins  # noqa: E402
from nsgablack.utils.parallel import with_parallel_evaluation  # noqa: E402
from nsgablack.utils.viz import launch_from_builder  # noqa: E402
from nsgablack.utils.context.context_keys import KEY_STEP  # noqa: E402
from nsgablack.utils.extension_contracts import normalize_candidates, stack_population  # noqa: E402

from refactor_bias import build_production_bias_module
from refactor_data import load_production_data
from refactor_pipeline import build_schedule_pipeline
from refactor_problem import ProductionConstraints, ProductionSchedulingProblem


_PROBLEM_FACTORY_CACHE = {}


def _project_schedule_material_feasible(problem, schedule: np.ndarray) -> np.ndarray:
    """Hard projection: enforce day-by-day material feasibility (shortage == 0)."""
    sched = np.asarray(schedule, dtype=float).copy()
    sched = np.clip(sched, 0.0, float(problem.constraints.max_production_per_machine))
    machines, days = sched.shape
    if machines != int(problem.machines) or days != int(problem.days):
        return sched
    bom = np.asarray(problem.data.bom_matrix, dtype=float)
    supply = np.asarray(problem.data.supply_matrix, dtype=float)
    current_stock = np.zeros(int(problem.materials), dtype=float)
    for day in range(days):
        current_stock += supply[:, day]
        day_prod = sched[:, day].copy()
        order = np.argsort(-day_prod)  # keep larger planned outputs first
        for m in order:
            prod = float(day_prod[m])
            if prod <= 0.0:
                continue
            req = bom[m, :]
            idx = req > 0
            if not np.any(idx):
                continue
            feasible = float(np.min(current_stock[idx] / np.maximum(req[idx], 1e-12)))
            if feasible < prod:
                day_prod[m] = max(0.0, feasible)
            consume = req * float(day_prod[m])
            current_stock = np.maximum(0.0, current_stock - consume)
        sched[:, day] = day_prod
    return sched


def _project_candidate_material_feasible(problem, x: np.ndarray) -> np.ndarray:
    schedule = problem.decode_schedule(np.asarray(x, dtype=float))
    projected = _project_schedule_material_feasible(problem, schedule)
    return projected.reshape(-1)


class StrictFeasibleProductionSolver(ComposableSolver):
    """Composable solver with hard material-feasible filtering before adapter update."""

    def __init__(self, *args, strict_constraint_tol: float = 1e-9, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.strict_constraint_tol = float(strict_constraint_tol)

    def step(self) -> None:
        if self.adapter is None:
            return
        context = self.build_context()
        context[KEY_STEP] = self.generation
        proposed = self.adapter.coerce_candidates(self.adapter.propose(self, context))
        candidates = normalize_candidates(
            proposed,
            dimension=self.dimension,
            owner=getattr(self.adapter, "name", "adapter"),
        )
        if len(candidates) > 0 and self.representation_pipeline is not None:
            repair = getattr(self.representation_pipeline, "repair", None)
            if repair is not None:
                if hasattr(self.representation_pipeline, "repair_batch"):
                    contexts = [context] * len(candidates)
                    candidates = self.representation_pipeline.repair_batch(candidates, contexts=contexts)
                else:
                    candidates = [self.repair_candidate(cand, context) for cand in candidates]
        if candidates is None:
            return
        try:
            candidate_count = len(candidates)
        except Exception:
            candidates = [candidates]  # type: ignore[list-item]
            candidate_count = 1
        if candidate_count <= 0:
            return

        # Step-2: strict projection after repair to ensure material feasibility.
        candidates = [_project_candidate_material_feasible(self.problem, np.asarray(c, dtype=float)) for c in candidates]

        population_all = stack_population(candidates, name="StrictFeasibleProductionSolver.population")
        objectives_all, violations_all = self.evaluate_population(population_all)

        # Step-1: hard filter infeasible candidates (all constraints).
        selected_mask = np.ones(len(population_all), dtype=bool)
        if violations_all is not None and len(violations_all) == len(population_all):
            try:
                vio = np.asarray(violations_all, dtype=float).reshape(len(population_all), -1)
                finite_mask = np.all(np.isfinite(vio), axis=1)
                feasible_mask = np.all(vio <= float(self.strict_constraint_tol), axis=1)
                selected_mask = finite_mask & feasible_mask
            except Exception:
                selected_mask = np.ones(len(population_all), dtype=bool)
        if np.any(selected_mask):
            self.population = np.asarray(population_all[selected_mask], dtype=float)
            self.objectives = np.asarray(objectives_all[selected_mask], dtype=float)
            self.constraint_violations = np.asarray(violations_all[selected_mask], dtype=float)
            strict_fallback = False
        else:
            self.population = population_all
            self.objectives = objectives_all
            self.constraint_violations = violations_all
            strict_fallback = True

        self.last_step_summary = self._summarize_step(self.objectives, self.constraint_violations)
        self.last_step_summary["num_candidates_raw"] = int(len(population_all))
        self.last_step_summary["num_candidates_feasible"] = int(len(self.population))
        self.last_step_summary["strict_feasible_fallback"] = bool(strict_fallback)
        self._update_best(self.population, self.objectives, self.constraint_violations)
        self.adapter.update(
            self,
            self.population,
            self.objectives,
            self.constraint_violations,
            context,
        )


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
            # Explicit context contract: this plugin only reports runtime progress.
            context_requires = ()
            context_provides = ()
            context_mutates = ()
            context_cache = ()
            context_notes = (
                "Console progress reporter; reads solver runtime state via hooks and writes no context fields.",
            )

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
                    best_total_output = None
                    best_constraint_violation = None
                    try:
                        bx = getattr(solver, "best_x", None)
                        problem = getattr(solver, "problem", None)
                        if bx is not None and problem is not None and hasattr(problem, "evaluate"):
                            obj = np.asarray(problem.evaluate(np.asarray(bx, dtype=float)), dtype=float).reshape(-1)
                            if obj.size >= 1 and np.isfinite(obj[0]):
                                best_total_output = float(-obj[0])
                            if hasattr(problem, "evaluate_constraints"):
                                cons = np.asarray(problem.evaluate_constraints(np.asarray(bx, dtype=float)), dtype=float).reshape(-1)
                                if cons.size == 0:
                                    best_constraint_violation = 0.0
                                else:
                                    finite = cons[np.isfinite(cons)]
                                    if finite.size > 0:
                                        best_constraint_violation = float(np.max(np.maximum(0.0, finite)))
                    except Exception:
                        best_total_output = None
                        best_constraint_violation = None

                    out_str = (
                        f"{best_total_output:.6g}" if isinstance(best_total_output, (float, int)) else "n/a"
                    )
                    vio_str = (
                        f"{best_constraint_violation:.6g}"
                        if isinstance(best_constraint_violation, (float, int))
                        else "n/a"
                    )
                    print(
                        f"[step {generation:04d}] elapsed={elapsed:8.1f}s  last_step={dt:6.2f}s  "
                        f"candidates={n}  best_score={best:.6g}  "
                        f"best_total_output={out_str}  best_constraint_violation={vio_str}"
                    )

        self._plugin = _Impl(report_every=report_every)

    def __getattr__(self, name):
        return getattr(self._plugin, name)


class ProductionExportPlugin:
    """Export best schedules and Pareto batch at solver finish (UI/CLI consistent)."""

    def __init__(self, problem, args) -> None:
        from nsgablack.plugins import Plugin

        class _Impl(Plugin):
            context_requires = ()
            context_provides = ()
            context_mutates = ()
            context_cache = ()
            context_notes = (
                "Exports production schedules at run end; does not mutate solver context.",
            )

            def __init__(self, problem, args):
                super().__init__(name="production_export")
                self.problem = problem
                self.args = args

            def on_solver_finish(self, _result):
                if bool(getattr(self.args, "no_export", False)):
                    return
                solver = getattr(self, "solver", None)
                if solver is None:
                    return
                individuals, objectives = _extract_pareto(solver)
                if individuals is None or objectives is None:
                    return
                choices = _choose_pareto_solutions(self.problem, individuals, objectives)
                base_export = Path(self.args.export) if getattr(self.args, "export", None) else None
                supply_path = getattr(getattr(self.problem, "data", None), "supply_path", None)
                supply_tag = _supply_tag_from_path(supply_path)
                for label, chosen, _obj in choices:
                    schedule = self.problem.decode_schedule(chosen)
                    schedule = _project_schedule_material_feasible(self.problem, schedule)
                    export_path = _resolve_export_path(base_export, label, supply_tag=supply_tag)
                    _export_schedule(export_path, schedule)
                    cons = self.problem.evaluate_constraints(schedule.reshape(-1))
                    cons_arr = np.asarray(cons, dtype=float).reshape(-1)
                    is_feasible = bool(np.all(cons_arr <= 1e-9))
                    total_output = float(np.sum(schedule))
                    _write_export_summary(
                        export_path=export_path,
                        label=label,
                        supply_path=(str(supply_path) if supply_path is not None else "(unknown)"),
                        feasible=is_feasible,
                        constraints=cons_arr.tolist(),
                        total_output=total_output,
                        days=int(schedule.shape[1]),
                    )
                    print(
                        f"[export] saved {label}: {export_path} "
                        f"feasible={is_feasible} total_output={total_output:.6g} "
                        f"supply={supply_path if supply_path is not None else '(unknown)'}"
                    )
                limit = int(getattr(self.args, "pareto_export", -1))
                if limit != 0:
                    exported = _export_pareto_batch(
                        self.problem,
                        individuals,
                        objectives,
                        base_export,
                        mode=str(getattr(self.args, "pareto_export_mode", "crowding")),
                        limit=limit,
                    )
                    if exported:
                        print(f"[export] Pareto batch exported: {exported}")

        self._plugin = _Impl(problem, args)

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
        root = base_dir / f"integrated_result_pareto_{ts}"
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
        schedule = _project_schedule_material_feasible(problem, schedule)
        obj_vals = problem.evaluate(schedule.reshape(-1))
        summary = problem.summarize_schedule(schedule)
        export_path = export_root / f"{label}{ext}"
        _export_schedule(export_path, schedule)
        row = {"label": label, "file": str(export_path)}
        for j, value in enumerate(obj_vals):
            row[f"obj{j}"] = float(value)
        row.update(summary)
        rows.append(row)

    if rows:
        import pandas as pd

        summary_path = _resolve_summary_path(export_root)
        df = pd.DataFrame(rows)
        df.to_csv(summary_path, index=False)
    return len(rows)


def _default_export_path(prefix: str = "integrated_result", label: Optional[str] = None) -> Path:
    base_dir = Path(__file__).resolve().parents[1]
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    if label:
        return base_dir / f"{prefix}_{label}_{ts}.xlsx"
    return base_dir / f"{prefix}_{ts}.xlsx"


def _resolve_export_path(base: Optional[Path], label: str, supply_tag: Optional[str] = None) -> Path:
    suffix = f"_{supply_tag}" if supply_tag else ""
    if base is None:
        p = _default_export_path(label=label)
        if suffix:
            return p.with_name(f"{p.stem}{suffix}{p.suffix}")
        return p
    if base.suffix:
        return base.with_name(f"{base.stem}_{label}{suffix}{base.suffix}")
    p = _default_export_path(label=label)
    name = f"{p.stem}{suffix}{p.suffix}" if suffix else p.name
    return base / name


def _supply_tag_from_path(path: Optional[Path | str]) -> Optional[str]:
    if path is None:
        return None
    try:
        stem = Path(path).stem
    except (TypeError, ValueError):
        return None
    # Keep filename safe and short to avoid unwieldy paths.
    tag = re.sub(r"[^A-Za-z0-9_-]+", "_", str(stem)).strip("_")
    if not tag:
        return None
    return f"src-{tag[:28]}"


def _write_export_summary(
    *,
    export_path: Path,
    label: str,
    supply_path: str,
    feasible: bool,
    constraints: list[float],
    total_output: float,
    days: int,
) -> None:
    summary_path = export_path.with_suffix(".summary.json")
    payload = {
        "label": str(label),
        "export_file": str(export_path),
        "supply_path": str(supply_path),
        "feasible": bool(feasible),
        "constraints": [float(x) for x in constraints],
        "max_violation": float(max([0.0] + [max(0.0, float(v)) for v in constraints])),
        "total_output": float(total_output),
        "days": int(days),
    }
    summary_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _export_schedule(path: Path, schedule: np.ndarray) -> None:
    import pandas as pd

    schedule = np.asarray(schedule, dtype=float)
    schedule = np.clip(np.floor(schedule), 0, None).astype(int)
    machines, days = schedule.shape

    data = {
        "Day_Index": list(range(days)),
        "Date": [f"Day{day + 1}" for day in range(days)],
    }
    for m in range(machines):
        data[f"Machine{m}"] = schedule[m, :].tolist()

    df = pd.DataFrame(data)
    if path.suffix.lower() == ".xlsx":
        # Keep a stable sheet name for downstream visualization scripts.
        df.to_excel(path, index=False, sheet_name="production_plan")
    else:
        df.to_csv(path, index=False)


def _extract_pareto(solver_or_result) -> tuple[Optional[np.ndarray], Optional[np.ndarray]]:
    """
    Normalize Pareto outputs from either:
    - EvolutionSolver result dict
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

    roles = []
    if str(getattr(args, "explorer_adapter", "moead")).lower() == "random":
        roles.append(
            RoleSpec(
                name="explorer",
                adapter=lambda uid: ProductionRandomSearchAdapter(batch_size=max(4, explorer_batch // 4)),
                n_units=4,
                weight=1.0,
            )
        )
    else:
        moead_pop = max(32, int(getattr(args, "moead_pop_size", max(64, args.pop_size // 2))))
        moead_neighbor = max(2, int(getattr(args, "moead_neighborhood", 20)))
        moead_nr = max(1, int(getattr(args, "moead_nr", 2)))
        moead_delta = float(getattr(args, "moead_delta", 0.9))
        roles.append(
            RoleSpec(
                name="explorer",
                adapter=lambda uid: MOEADAdapter(
                    MOEADConfig(
                        population_size=moead_pop,
                        neighborhood_size=moead_neighbor,
                        batch_size=max(4, explorer_batch),
                        delta=moead_delta,
                        nr=moead_nr,
                        variation="pipeline",
                        random_seed=(None if args.seed is None else int(args.seed) + int(uid)),
                    )
                ),
                n_units=1,
                weight=1.0,
            )
        )
    if str(getattr(args, "exploiter_adapter", "vns")).lower() == "local":
        roles.append(
            RoleSpec(
                name="exploiter",
                adapter=lambda uid: ProductionLocalSearchAdapter(batch_size=max(2, exploiter_batch // 2)),
                n_units=2,
                weight=1.0,
            )
        )
    else:
        vns_batch = max(4, int(getattr(args, "vns_batch_size", exploiter_batch)))
        vns_kmax = max(1, int(getattr(args, "vns_k_max", 4)))
        vns_sigma = float(getattr(args, "vns_base_sigma", 0.2))
        roles.append(
            RoleSpec(
                name="exploiter",
                adapter=lambda uid: VNSAdapter(
                    VNSConfig(
                        batch_size=vns_batch,
                        k_max=vns_kmax,
                        base_sigma=vns_sigma,
                        scale=1.6,
                        objective_aggregation="sum",
                    )
                ),
                n_units=1,
                weight=1.0,
            )
        )

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

    base_solver_cls = ComposableSolver if bool(getattr(args, "allow_infeasible_update", False)) else StrictFeasibleProductionSolver
    SolverClass = with_parallel_evaluation(base_solver_cls)
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
        parallel_thread_bias_isolation=str(args.parallel_thread_bias_isolation),
        parallel_problem_factory=factory,
    )
    if not bool(getattr(args, "no_run_logs", False)):
        repo_root = Path(__file__).resolve().parents[1]
        run_dir = Path(args.run_dir) if getattr(args, "run_dir", None) else (repo_root / "runs" / "production_schedule")
        run_id = str(args.run_id) if getattr(args, "run_id", None) else datetime.now().strftime("%Y%m%d_%H%M%S")
        run_dir = run_dir.expanduser().resolve()
        run_dir.mkdir(parents=True, exist_ok=True)
        attach_default_observability_plugins(
            solver,
            output_dir=str(run_dir),
            run_id=str(run_id),
            overwrite=True,
            enable_pareto_archive=False,
            enable_benchmark=True,
            benchmark_log_every=int(getattr(args, "log_every", 1) or 1),
            benchmark_flush_every=10,
            enable_module_report=True,
            write_bias_markdown=not bool(getattr(args, "no_bias_md", False)),
            enable_profiler=not bool(getattr(args, "no_profile", False)),
            enable_decision_trace=not bool(getattr(args, "no_decision_trace", False)),
            decision_trace_flush_every=max(1, int(getattr(args, "decision_trace_flush_every", 1))),
        )
        print(f"[run] logs_dir={run_dir} run_id={run_id}")
    solver.add_plugin(ParetoArchivePlugin())
    solver.add_plugin(ConsoleProgressPlugin(report_every=args.report_every))
    solver.add_plugin(ProductionExportPlugin(problem, args))
    solver.set_max_steps(int(args.generations))
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
    if choices:
        print(f"Selected key Pareto candidates: {len(choices)} (export handled by production_export plugin)")


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
    parser.add_argument("--max-prod", type=int, default=10000)
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
    parser.add_argument("--generations", type=int, default=30)
    parser.add_argument("--crossover-rate", type=float, default=0.85)
    parser.add_argument("--mutation-rate", type=float, default=0.15)
    parser.add_argument("--report-every", type=int, default=10)
    parser.add_argument("--run-dir", type=str, default=None, help="Auto logs dir for benchmark/module reports.")
    parser.add_argument("--run-id", type=str, default=None, help="Run id for reports (default: timestamp).")
    parser.add_argument("--log-every", type=int, default=1, help="BenchmarkHarness CSV log frequency.")
    parser.add_argument("--no-bias-md", action="store_true", help="Disable writing bias.md in module report.")
    parser.add_argument("--no-run-logs", action="store_true", help="Disable automatic benchmark/module reports.")
    parser.add_argument("--no-profile", action="store_true", help="Disable ProfilerPlugin output in run logs.")
    parser.add_argument(
        "--no-decision-trace",
        action="store_true",
        help="Disable DecisionTracePlugin output in run logs.",
    )
    parser.add_argument(
        "--decision-trace-flush-every",
        type=int,
        default=1,
        help="Decision trace summary flush interval (generations).",
    )
    parser.add_argument("--no-export", action="store_true", help="Disable exporting schedules (no Excel/CSV output).")
    parser.add_argument("--comm-interval", type=int, default=5)
    parser.add_argument("--adapt-interval", type=int, default=20)
    parser.add_argument(
        "--explorer-adapter",
        choices=["moead", "random"],
        default="moead",
        help="Explorer role adapter: moead (default) or random search.",
    )
    parser.add_argument("--vns-batch-size", type=int, default=48, help="VNS candidates per step.")
    parser.add_argument("--vns-k-max", type=int, default=4, help="VNS neighborhood depth.")
    parser.add_argument("--vns-base-sigma", type=float, default=0.2, help="VNS initial mutation sigma.")
    parser.add_argument(
        "--exploiter-adapter",
        choices=["vns", "local"],
        default="vns",
        help="Exploiter role adapter: vns (default) or local search.",
    )
    parser.add_argument("--moead-pop-size", type=int, default=48, help="MOEA/D subproblem population size.")
    parser.add_argument("--moead-neighborhood", type=int, default=20, help="MOEA/D neighborhood size.")
    parser.add_argument("--moead-delta", type=float, default=0.9, help="MOEA/D neighbor sampling probability.")
    parser.add_argument("--moead-nr", type=int, default=2, help="MOEA/D max replacements per offspring.")
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
    parser.add_argument(
        "--parallel-thread-bias-isolation",
        choices=["deepcopy", "disable_cache", "off"],
        default="deepcopy",
        help="Thread backend bias isolation strategy (deepcopy recommended).",
    )
    parser.add_argument(
        "--allow-infeasible-update",
        action="store_true",
        help="Disable strict material-feasible candidate filtering before adapter update.",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=None,
        help="Random seed. Default: None (use runtime random seed).",
    )
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
    if int(getattr(args, "days", 31)) != 31:
        print(f"[run] override --days={args.days} ignored; enforcing 31-day window (day0..30).")
    args.days = 31
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

    if int(getattr(args, "days", 31)) != 31:
        print(f"[run] override --days={args.days} ignored; enforcing 31-day window (day0..30).")
    args.days = 31
    print(
        "[run] solver=multi-agent "
        f"parallel={bool(args.parallel)} backend={args.parallel_backend} workers={args.parallel_workers} "
        f"generations={args.generations} pop_size={args.pop_size} days=31"
    )
    print("[run] production_window=day0..30 (inclusive)")
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

