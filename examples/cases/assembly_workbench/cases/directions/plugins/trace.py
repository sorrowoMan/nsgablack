"""有界只读轨迹；正式权威结果仍由标准 Case/Project 发布。"""
from collections.abc import Mapping
from dataclasses import asdict
import json
from pathlib import Path

from blackbase.participation import ParticipationContract
from nsgablack.adapters import StrategyOrigin
from nsgablack.adapters.subpools import adapter_path
from nsgablack.plugins.base import Plugin
from nsgablack.utils.engineering.file_io import atomic_write_text


def data_copy(value):
    return json.loads(json.dumps(value, allow_nan=False))


class DirectionTrace(Plugin):
    participation = ParticipationContract(vetoes=("finalization",))
    state_recovery_level = "L1"
    state_recovery_notes = "Bounded committed observations with an explicit JSON state codec."
    context_requires = context_provides = context_mutates = context_cache = ()
    context_notes = ("Read-only pool, task and Unit observations; never constructs a Unit.",)

    def __init__(self, *, output_dir, settings):
        super().__init__(name="direction_trace")
        self.output_dir, self.settings = Path(output_dir), settings
        self.run_id, self.initial, self.records = None, None, []
        self.last_sequence, self.last_evaluations = 0, 0

    def _roles(self):
        root, pool = self.solver.adapter, self.solver.solution_pool
        rows = []
        for unit in root.units:
            wrapper, inner = unit.adapter, unit.adapter.inner
            path = adapter_path(root, inner)
            views = pool.subpools_created_by(path)
            rows.append(dict(role=unit.role, owner_path=list(path), adapter_type=type(inner).__name__,
                task=wrapper.task_status,
                unit_exists=getattr(inner, "algorithm_unit", None) is not None,
                current_unit_exists=getattr(inner, "current_unit", None) is not None,
                neighborhood_unit_exists=getattr(inner, "neighborhood_unit", None) is not None,
                views=[dict(descriptor=pool.subpool_descriptor(name),
                    projection=pool.subpool_metadata(name).get("projection")) for name in views]))
        return rows

    def on_solver_init(self, solver):
        if self.run_id != solver.run_session.run_id:
            self.run_id, self.records = solver.run_session.run_id, []
            self.last_sequence, self.last_evaluations = 0, 0
            self.initial = dict(clock=solver.solution_pool.timestamp.as_dict(), roles=self._roles())

    def on_generation_committed(self, generation, outcome):
        del generation
        if not outcome.get("committed", False) or len(self.records) >= self.settings.max_steps:
            raise ValueError("direction trace expects one bounded committed observation")
        solver, pool = self.solver, self.solver.solution_pool
        refs = tuple(ref for ref in pool.select()
                     if pool.stamp_for(ref).sequence > self.last_sequence)
        phases = {origin.phase for state in pool.read(refs).semantic_states
                  for origin in StrategyOrigin.from_candidate(state)}
        if not phases or (len(phases) > 1 and phases != {"coarse", "fine"}):
            raise ValueError("direction plan observed unexpected proposal phases")
        phase = next(iter(phases)) if len(phases) == 1 else "parallel"
        evaluations = int(solver.evaluation_count)
        self.records.append(dict(step=int(solver.run_progress_steps), phase=phase, phases=sorted(phases),
            evaluation_delta=evaluations - self.last_evaluations,
            evaluations=evaluations, clock=pool.timestamp.as_dict(),
            accepted_refs=[ref.as_dict() for ref in refs], roles=self._roles()))
        self.last_sequence, self.last_evaluations = pool.timestamp.sequence, evaluations

    def _values(self, refs):
        pool = self.solver.solution_pool
        raw_f, raw_v = pool.read_raw_feedback(refs)
        return dict(refs=[ref.as_dict() for ref in refs],
            candidates=pool.read(refs).numeric_matrix.tolist(),
            raw_objectives=raw_f.tolist(), raw_violations=raw_v.tolist())

    def _summary(self):
        """Read committed results without evaluating or changing pool owners."""
        solver, root, pool = self.solver, self.solver.adapter, self.solver.solution_pool
        tasks, views, receipts = {}, {}, {}
        for unit in root.units:
            wrapper, inner = unit.adapter, unit.adapter.inner
            tasks[unit.role] = wrapper.task_status
            receipts[unit.role] = wrapper.get_state()["pool_task"].get("result_views", [])
            path = adapter_path(root, inner)
            views[unit.role] = [dict(name=name, metadata=pool.subpool_metadata(name),
                descriptor=pool.subpool_descriptor(name), **self._values(pool.subpool_refs(name)))
                for name in pool.subpools_created_by(path)]
        producer = next(unit.adapter.inner for unit in root.units if unit.role == "moead")
        population = self._values(producer.get_population_solution_refs(solver))
        population["adapter_objectives"] = producer.pop_F.tolist()
        archive = solver.get_plugin("pareto_archive")
        pareto = dict(size=archive.total_archive_size(),
            candidates=[] if archive.archive_X is None else archive.archive_X.tolist(),
            raw_objectives=[] if archive.archive_F is None else archive.archive_F.tolist())
        returned_roles = ("coarse", "fine") if self.settings.refinement_layout == "parallel" else ("fine",)
        final_refs = tuple(ref for role in returned_roles for ref in root.get_pool_task_results(solver, role))
        return dict(schema="assembly_workbench.directions/v1", run_id=self.run_id,
            settings=asdict(self.settings), refinement_layout=self.settings.refinement_layout,
            returned_roles=list(returned_roles), logical_steps=int(solver.run_progress_steps),
            evaluations=int(solver.evaluation_count), plan_completed=root.cursor.completed,
            pool_id=pool.pool_id, clock=pool.timestamp.as_dict(), tasks=tasks,
            views=views, result_receipts=receipts, final_results=self._values(final_refs),
            final_population=population, pareto=pareto,
            resource_binding_current=bool(getattr(solver, "resource_binding_audit", {}).get("current", False)))

    def on_solver_finalization_prepare(self, result):
        del result
        runtime = self.solver.case_runtime
        if runtime is None:
            return
        summary = self._summary()
        runtime.begin_finalization_transaction("case_finalization").publish(
            "summary", summary, serializer="json", kind="case-summary",
            metadata={"schema": summary["schema"]})

    def on_solver_finalized(self, result):
        del result
        summary = self._summary()
        trace = {**self.get_state(), "summary": summary}
        for name, payload in (("trace.json", trace), ("summary.json", summary)):
            atomic_write_text(self.output_dir / name,
                json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False))

    def get_state(self):
        return data_copy(dict(schema="assembly_workbench.direction_trace/v1",
            max_records=self.settings.max_steps, run_id=self.run_id, initial=self.initial,
            records=self.records, last_sequence=self.last_sequence,
            last_evaluations=self.last_evaluations))

    def set_state(self, state):
        if not isinstance(state, Mapping) or state.get("schema") != "assembly_workbench.direction_trace/v1":
            raise ValueError("invalid direction trace state")
        saved = data_copy(dict(state))
        if saved.get("max_records") != self.settings.max_steps or not isinstance(saved.get("records"), list):
            raise ValueError("direction trace capacity mismatch")
        if len(saved["records"]) > self.settings.max_steps:
            raise ValueError("direction trace capacity exceeded")
        self.run_id, self.initial, self.records = saved["run_id"], saved["initial"], saved["records"]
        self.last_sequence, self.last_evaluations = saved["last_sequence"], saved["last_evaluations"]
