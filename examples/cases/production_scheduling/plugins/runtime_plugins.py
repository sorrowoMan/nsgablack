"""Case-local runtime plugins for production_scheduling."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Callable, Optional

import numpy as np

from nsgablack.plugins import Plugin

ExtractParetoFn = Callable[[Any], tuple[Optional[np.ndarray], Optional[np.ndarray]]]
ChooseParetoFn = Callable[[Any, np.ndarray, np.ndarray], list[tuple[str, np.ndarray, np.ndarray]]]
ProjectScheduleFn = Callable[[Any, np.ndarray], np.ndarray]
ResolveExportPathFn = Callable[[Optional[Path], str, Optional[str]], Path]
ExportScheduleFn = Callable[[Path, np.ndarray], None]
WriteExportSummaryFn = Callable[..., None]
ExportParetoBatchFn = Callable[[Any, np.ndarray, np.ndarray, Optional[Path], str, int], int]
SupplyTagFn = Callable[[Optional[Path | str]], Optional[str]]


class ConsoleProgressPlugin(Plugin):
    """Minimal console progress to avoid the 'looks stuck' feeling."""

    context_requires = ()
    context_provides = ()
    context_mutates = ()
    context_cache = ()
    context_notes = (
        "Console progress reporter; reads solver runtime state via hooks and writes no context fields.",
    )

    def __init__(self, report_every: int = 10):
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
        except (TypeError, ValueError, AttributeError):
            n = None

        elapsed = (now - self._t0) if self._t0 is not None else 0.0
        if best is None:
            print(f"[step {generation:04d}] elapsed={elapsed:8.1f}s  last_step={dt:6.2f}s  candidates={n}")
            return

        best_total_output, best_constraint_violation = self._compute_best_metrics(solver)
        out_str = f"{best_total_output:.6g}" if isinstance(best_total_output, (float, int)) else "n/a"
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

    @staticmethod
    def _compute_best_metrics(solver) -> tuple[Optional[float], Optional[float]]:
        bx = getattr(solver, "best_x", None)
        problem = getattr(solver, "problem", None)
        if bx is None or problem is None or not hasattr(problem, "evaluate"):
            return None, None
        try:
            obj = np.asarray(problem.evaluate(np.asarray(bx, dtype=float)), dtype=float).reshape(-1)
            best_total_output = float(-obj[0]) if obj.size >= 1 and np.isfinite(obj[0]) else None

            best_constraint_violation = None
            if hasattr(problem, "evaluate_constraints"):
                cons = np.asarray(problem.evaluate_constraints(np.asarray(bx, dtype=float)), dtype=float).reshape(-1)
                if cons.size == 0:
                    best_constraint_violation = 0.0
                else:
                    finite = cons[np.isfinite(cons)]
                    if finite.size > 0:
                        best_constraint_violation = float(np.max(np.maximum(0.0, finite)))
            return best_total_output, best_constraint_violation
        except (TypeError, ValueError, AttributeError):
            return None, None


class ProductionExportPlugin(Plugin):
    """Export best schedules and Pareto batch at solver finish (UI/CLI consistent)."""

    context_requires = ()
    context_provides = ()
    context_mutates = ()
    context_cache = ()
    context_notes = (
        "Exports production schedules at run end; does not mutate solver context.",
    )

    def __init__(
        self,
        problem,
        args,
        *,
        extract_pareto: ExtractParetoFn,
        choose_pareto_solutions: ChooseParetoFn,
        project_schedule_material_feasible: ProjectScheduleFn,
        resolve_export_path: ResolveExportPathFn,
        export_schedule: ExportScheduleFn,
        write_export_summary: WriteExportSummaryFn,
        export_pareto_batch: ExportParetoBatchFn,
        supply_tag_from_path: SupplyTagFn,
    ) -> None:
        super().__init__(name="production_export")
        self.problem = problem
        self.args = args
        self._extract_pareto = extract_pareto
        self._choose_pareto_solutions = choose_pareto_solutions
        self._project_schedule_material_feasible = project_schedule_material_feasible
        self._resolve_export_path = resolve_export_path
        self._export_schedule = export_schedule
        self._write_export_summary = write_export_summary
        self._export_pareto_batch = export_pareto_batch
        self._supply_tag_from_path = supply_tag_from_path

    def on_solver_finish(self, _result):
        if bool(getattr(self.args, "no_export", False)):
            return
        solver = getattr(self, "solver", None)
        if solver is None:
            return
        individuals, objectives = self._extract_pareto(solver)
        if individuals is None or objectives is None:
            return

        choices = self._choose_pareto_solutions(self.problem, individuals, objectives)
        base_export = Path(self.args.export) if getattr(self.args, "export", None) else None
        supply_path = getattr(getattr(self.problem, "data", None), "supply_path", None)
        supply_tag = self._supply_tag_from_path(supply_path)

        for label, chosen, _obj in choices:
            schedule = self.problem.decode_schedule(chosen)
            schedule = self._project_schedule_material_feasible(self.problem, schedule)
            export_path = self._resolve_export_path(base_export, label, supply_tag=supply_tag)
            self._export_schedule(export_path, schedule)
            cons = self.problem.evaluate_constraints(schedule.reshape(-1))
            cons_arr = np.asarray(cons, dtype=float).reshape(-1)
            is_feasible = bool(np.all(cons_arr <= 1e-9))
            total_output = float(np.sum(schedule))
            self._write_export_summary(
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
            exported = self._export_pareto_batch(
                self.problem,
                individuals,
                objectives,
                base_export,
                mode=str(getattr(self.args, "pareto_export_mode", "crowding")),
                limit=limit,
            )
            if exported:
                print(f"[export] Pareto batch exported: {exported}")
