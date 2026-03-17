"""Case-local plugin: export adjusted supply artifacts at solver finish."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np

from nsgablack.plugins import Plugin

if TYPE_CHECKING:
    from problem import SupplyEventShiftProblem


class SupplyAdjustmentExportPlugin(Plugin):
    """Export selected adjusted supply table and move log at run end."""

    context_requires = ()
    context_provides = ()
    context_mutates = ()
    context_cache = ()
    context_notes = (
        "Exports adjusted supply/move log; no runtime context mutation.",
    )

    def __init__(self, *, case_problem: "SupplyEventShiftProblem", output_dir: Path, run_id: str) -> None:
        super().__init__(name="supply_adjustment_export")
        self.case_problem = case_problem
        self.output_dir = output_dir
        self.run_id = run_id

    def on_solver_finish(self, result):
        solver = getattr(self, "solver", None)
        if solver is None:
            return

        x = getattr(solver, "best_x", None)
        if x is None and isinstance(result, dict):
            pareto = result.get("pareto_solutions")
            if isinstance(pareto, dict) and "individuals" in pareto:
                inds = pareto.get("individuals")
                objs = pareto.get("objectives")
                try:
                    inds_arr = np.asarray(inds, dtype=float)
                    if inds_arr.ndim == 2 and inds_arr.shape[0] > 0:
                        if objs is not None:
                            obj_arr = np.asarray(objs, dtype=float)
                            if obj_arr.ndim == 2 and obj_arr.shape[0] == inds_arr.shape[0]:
                                # Use a simple scalarization only to pick one export candidate.
                                ref = obj_arr - np.min(obj_arr, axis=0, keepdims=True)
                                score = np.sum(ref, axis=1)
                                x = inds_arr[int(np.argmin(score))]
                            else:
                                x = inds_arr[0]
                        else:
                            x = inds_arr[0]
                except Exception:
                    x = None
        if x is None:
            try:
                pop_arr, obj_arr, _ = self.get_population_snapshot(solver)
                if pop_arr.ndim == 2 and pop_arr.shape[0] > 0:
                    if obj_arr.ndim == 2 and obj_arr.shape[0] == pop_arr.shape[0]:
                        idx = int(np.argmin(np.sum(obj_arr, axis=1)))
                    else:
                        idx = 0
                    x = pop_arr[idx]
            except Exception:
                x = None
        if x is None:
            return

        out_xlsx = self.output_dir / f"adjusted_supply_{self.run_id}.xlsx"
        out_moves = self.output_dir / f"adjusted_supply_moves_{self.run_id}.csv"

        shifts, _ = self.case_problem.export_adjusted_supply(np.asarray(x, dtype=float), out_xlsx)
        move_df = self.case_problem.export_move_log(shifts, out_moves)

        moved_events = int((shifts > 0).sum())
        moved_days = int(shifts.sum())
        print(f"[export] adjusted_supply={out_xlsx}")
        print(f"[export] move_log={out_moves} rows={len(move_df)} moved_events={moved_events} moved_days={moved_days}")
