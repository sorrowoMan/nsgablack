"""Case-local plugin: export adjusted supply artifacts at solver finish."""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np

from blackbase.resources import DataRef
from nsgablack.plugins import Plugin
from reporting import write_supply_adjustment_audit_report

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

        selected = self._select_export_candidate(solver)
        if selected is not None:
            x, selected_objectives = selected
        else:
            x = getattr(solver, "best_x", None)
            selected_objectives = self._lookup_objectives_for_candidate(solver, x)
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
                                selected_idx = self._select_index(inds_arr, obj_arr)
                                x = inds_arr[selected_idx]
                                selected_objectives = obj_arr[selected_idx]
                            else:
                                x = inds_arr[0]
                                selected_objectives = None
                        else:
                            x = inds_arr[0]
                            selected_objectives = None
                except (TypeError, ValueError, IndexError):
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
                    if obj_arr.ndim == 2 and obj_arr.shape[0] > idx:
                        selected_objectives = obj_arr[idx]
            except (TypeError, ValueError):
                x = None
        if x is None:
            return
        if selected_objectives is None:
            selected_objectives = self._lookup_objectives_for_candidate(solver, x)

        out_xlsx = self.output_dir / f"adjusted_supply_{self.run_id}.xlsx"
        out_moves = self.output_dir / f"adjusted_supply_moves_{self.run_id}.csv"
        out_audit = self.output_dir / f"adjusted_supply_audit_{self.run_id}.json"
        out_runtime = self.output_dir / f"l0_runtime_summary_{self.run_id}.json"

        shifts, _ = self.case_problem.export_adjusted_supply(np.asarray(x, dtype=float), out_xlsx)
        move_df = self.case_problem.export_move_log(shifts, out_moves)
        try:
            write_supply_adjustment_audit_report(
                self.case_problem,
                np.asarray(x, dtype=float),
                out_audit,
                objectives=selected_objectives,
                label="selected",
            )
        except Exception as exc:
            print(f"[audit] adjusted_supply: failed to write audit ({exc!r})")

        moved_events = int((shifts > 0).sum())
        moved_days = int(shifts.sum())
        artifact_refs = [
            DataRef.from_path(out_xlsx, kind="adjusted_supply", media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
            DataRef.from_path(out_moves, kind="move_log", media_type="text/csv"),
            DataRef.from_path(out_audit, kind="audit", media_type="application/json"),
        ]
        runtime_ref = self._write_runtime_summary(
            solver,
            out_runtime,
            artifact_refs=artifact_refs,
            selected_objectives=selected_objectives,
        )
        print(f"[export] adjusted_supply={out_xlsx}")
        print(f"[export] move_log={out_moves} rows={len(move_df)} moved_events={moved_events} moved_days={moved_days}")
        print(f"[export] audit={out_audit}")
        print(f"[export] l0_runtime_summary={out_runtime}")
        if runtime_ref is not None:
            print(f"[export] runtime_artifact_ref={runtime_ref.as_dict()}")

    def _select_export_candidate(self, solver):
        snapshot_population, snapshot_objectives, _ = self.get_population_snapshot(solver)
        candidate_sets = []
        for pop, obj in (
            (snapshot_population, snapshot_objectives),
            self._pareto_arrays(solver),
        ):
            try:
                pop_arr = np.asarray(pop, dtype=float)
                obj_arr = np.asarray(obj, dtype=float)
            except (TypeError, ValueError):
                continue
            if pop_arr.ndim != 2 or pop_arr.shape[0] == 0:
                continue
            if obj_arr.ndim == 1:
                obj_arr = obj_arr.reshape(-1, 1)
            if obj_arr.ndim != 2 or obj_arr.shape[0] != pop_arr.shape[0]:
                continue
            candidate_sets.append((pop_arr, obj_arr))
        if not candidate_sets:
            return None

        best_x = None
        best_obj = None
        best_score = float("inf")
        for pop_arr, obj_arr in candidate_sets:
            idx = self._select_index(pop_arr, obj_arr)
            score = self._score_candidate(pop_arr[idx], obj_arr[idx])
            if score < best_score:
                best_score = score
                best_x = pop_arr[idx]
                best_obj = obj_arr[idx]
        if best_x is None:
            return None
        return best_x, best_obj

    def _select_index(self, population, objectives) -> int:
        pop_arr = np.asarray(population, dtype=float)
        obj_arr = np.asarray(objectives, dtype=float)
        if obj_arr.ndim == 1:
            obj_arr = obj_arr.reshape(-1, 1)
        scores = [self._score_candidate(pop_arr[i], obj_arr[i]) for i in range(pop_arr.shape[0])]
        return int(np.argmin(np.asarray(scores, dtype=float)))

    def _score_candidate(self, x, objectives) -> float:
        obj = np.asarray(objectives, dtype=float).reshape(-1)
        output_term = float(obj[0]) if obj.size > 0 else 0.0
        moved_events = float(obj[1]) if obj.size > 1 else 0.0
        moved_days = float(obj[2]) if obj.size > 2 else 0.0
        moved_quantity_days = self._moved_quantity_days(x)
        return output_term + moved_events + (0.25 * moved_days) + (0.00005 * moved_quantity_days)

    def _moved_quantity_days(self, x) -> float:
        try:
            shifts = self.case_problem.decode_shifts(np.asarray(x, dtype=float))
        except (TypeError, ValueError, IndexError, AttributeError):
            return 0.0
        total = 0.0
        for i, shift in enumerate(shifts):
            s = int(shift)
            if s <= 0:
                continue
            try:
                total += float(self.case_problem.events[int(i)].quantity) * float(s)
            except (TypeError, ValueError, IndexError, AttributeError):
                continue
        return float(total)

    @staticmethod
    def _pareto_arrays(solver):
        pareto = getattr(solver, "pareto_solutions", None)
        if not isinstance(pareto, dict):
            return None, None
        return pareto.get("individuals"), pareto.get("objectives")

    def _lookup_objectives_for_candidate(self, solver, x):
        if x is None:
            return None
        try:
            target = np.asarray(x, dtype=float).reshape(-1)
        except (TypeError, ValueError):
            return None
        pareto = getattr(solver, "pareto_solutions", None)
        if not isinstance(pareto, dict):
            pareto = {}
        snapshot_population, snapshot_objectives, _ = self.get_population_snapshot(solver)

        for pop_obj in (
            (snapshot_population, snapshot_objectives),
            (
                pareto.get("individuals"),
                pareto.get("objectives"),
            ),
        ):
            pop, obj = pop_obj
            try:
                pop_arr = np.asarray(pop, dtype=float)
                obj_arr = np.asarray(obj, dtype=float)
            except (TypeError, ValueError):
                continue
            if pop_arr.ndim != 2 or pop_arr.shape[0] == 0 or pop_arr.shape[1] != target.size:
                continue
            if obj_arr.ndim == 1:
                obj_arr = obj_arr.reshape(-1, 1)
            if obj_arr.ndim != 2 or obj_arr.shape[0] != pop_arr.shape[0]:
                continue
            dist = np.linalg.norm(pop_arr - target.reshape(1, -1), axis=1)
            idx = int(np.argmin(dist))
            if np.allclose(pop_arr[idx], target, rtol=1e-8, atol=1e-8):
                return obj_arr[idx]

        best = getattr(solver, "best_objective", None)
        if best is not None:
            try:
                return np.asarray([float(best)], dtype=float)
            except (TypeError, ValueError, OverflowError):
                return None
        return None

    def _write_runtime_summary(self, solver, path: Path, *, artifact_refs, selected_objectives):
        evaluator = getattr(solver, "nested_parallel_evaluator", None)
        task_results = list(getattr(evaluator, "last_task_results", []) or [])
        worker_ids = sorted(
            {
                str(item.get("worker_id", ""))
                for item in task_results
                if isinstance(item, dict) and str(item.get("worker_id", ""))
            }
        )
        leases = []
        resource_contexts = []
        task_artifact_refs = []
        for item in task_results:
            if not isinstance(item, dict):
                continue
            lease_id = str(item.get("lease_id", "") or "")
            resource_context = dict(item.get("resource_context", {}) or {})
            if lease_id or resource_context.get("lease"):
                leases.append(
                    {
                        "task_id": str(item.get("task_id", "")),
                        "worker_id": str(item.get("worker_id", "")),
                        "lease_id": lease_id,
                        "lease": resource_context.get("lease"),
                    }
                )
            if resource_context:
                resource_contexts.append(
                    {
                        "task_id": str(item.get("task_id", "")),
                        "worker_id": str(item.get("worker_id", "")),
                        "resource_context": resource_context,
                    }
                )
            for ref in item.get("artifact_refs", []) or []:
                if isinstance(ref, dict):
                    task_artifact_refs.append(dict(ref))

        payload = dict(getattr(solver, "l0_runtime_summary", {}) or {})
        payload.setdefault("schema", "supply_adjustment_nested.l0_runtime_summary.v1")
        payload["selected_objectives"] = [] if selected_objectives is None else [float(x) for x in np.asarray(selected_objectives, dtype=float).reshape(-1)]
        payload["effective_runtime"] = {
            "evaluator": type(evaluator).__name__ if evaluator is not None else "",
            "last_run_id": str(getattr(evaluator, "last_run_id", "") or ""),
            "workers": worker_ids,
            "leases": leases,
            "resource_contexts": resource_contexts[-20:],
            "task_result_count": int(len(task_results)),
            "task_artifact_refs": task_artifact_refs,
        }
        payload["artifact_refs"] = [ref.as_dict() for ref in artifact_refs]

        report_path = Path(path)
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
        return DataRef.from_path(report_path, kind="l0_runtime_summary", media_type="application/json")
