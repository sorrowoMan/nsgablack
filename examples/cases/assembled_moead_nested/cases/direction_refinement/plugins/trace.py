"""只观察已提交状态，最终输出精确引用和原始反馈，供报告对账。"""
from collections.abc import Mapping
import json
from pathlib import Path
from blackbase.participation import ParticipationContract
from nsgablack.adapters.subpools import adapter_path
from nsgablack.plugins.base import Plugin
from nsgablack.utils.engineering.file_io import atomic_write_text


def data_copy(value):
    return json.loads(json.dumps(value, allow_nan=False))


class NestedTrace(Plugin):
    participation = ParticipationContract()
    state_recovery_level = "L1"
    state_recovery_notes = "Bounded JSON observations with an explicit data codec."
    context_notes = ("Read-only committed pool/task/Unit observations; never ensures a Unit.",)

    def __init__(self, *, output_dir, max_records):
        super().__init__(name="nested_trace")
        if type(max_records) is not int or max_records < 1:
            raise ValueError("max_records must be a positive integer")
        self.output_dir = Path(output_dir)
        self.max_records = max_records
        self.run_id, self.initial, self.records = None, None, []

    def _observe(self):
        solver, root = self.solver, self.solver.adapter
        pool = solver.solution_pool
        roles = []
        for instance in root.units:
            wrapper, inner = instance.adapter, instance.adapter.inner
            path = adapter_path(root, inner)
            roles.append({
                "role": instance.role, "owner_path": list(path),
                "adapter_type": type(inner).__name__, "task": wrapper.task_status,
                "unit_exists": getattr(inner, "algorithm_unit", None) is not None,
                "current_unit_exists": getattr(inner, "current_unit", None) is not None,
                "neighborhood_unit_exists": getattr(inner, "neighborhood_unit", None) is not None,
                "views": list(pool.subpools_created_by(path)),
            })
        return {"logical_steps": int(solver.run_progress_steps),
                "evaluations": int(solver.evaluation_count),
                "phase": root.get_runtime_context_projection(solver).get("phase"),
                "roles": roles}

    def on_solver_init(self, solver):
        if self.run_id != solver.run_session.run_id:
            self.run_id, self.records = solver.run_session.run_id, []
            self.initial = self._observe()

    def on_generation_committed(self, generation, outcome):
        del generation
        if not outcome.get("committed", False):
            raise ValueError("observer requires a committed generation")
        if len(self.records) >= self.max_records:
            raise RuntimeError("teaching trace capacity exhausted")
        self.records.append(self._observe())

    def on_solver_finalized(self, result):
        del result
        solver, pool = self.solver, self.solver.solution_pool
        final, views, aggregates = self._observe(), {}, {}
        for role in final["roles"]:
            entries = []
            for name in role["views"]:
                refs = pool.subpool_refs(name)
                raw_f, raw_v = pool.read_raw_feedback(refs)
                entries.append({"name": name, "metadata": pool.subpool_metadata(name),
                    "refs": [ref.as_dict() for ref in refs],
                    "candidates": pool.read(refs).numeric_matrix.tolist(),
                    "raw_objectives": raw_f.tolist(), "raw_violations": raw_v.tolist()})
            views[role["role"]] = entries
            output = role["task"]["output"]
            if output is not None:
                aggregates[role["role"]] = {"name": output,
                    "members": len(pool.subpool_refs(output))}
        moead = next(item.adapter.inner for item in solver.adapter.units if item.role == "moead")
        refs = moead.get_population_solution_refs(solver)
        raw_f, raw_v = pool.read_raw_feedback(refs)
        payload = {**self.get_state(), "final": final, "views": views, "aggregates": aggregates,
                   "final_population": {"refs": [ref.as_dict() for ref in refs],
                       "candidates": pool.read(refs).numeric_matrix.tolist(),
                       "raw_objectives": raw_f.tolist(), "raw_violations": raw_v.tolist(),
                       "adapter_objectives": moead.pop_F.tolist()}}
        atomic_write_text(self.output_dir / "trace.json",
                          json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False))

    def get_state(self):
        return data_copy({"schema": "assembled_moead_nested.trace/v1", "max_records": self.max_records,
                          "run_id": self.run_id,
                          "initial": self.initial, "records": self.records})

    def set_state(self, state):
        if not isinstance(state, Mapping) or state.get("schema") != "assembled_moead_nested.trace/v1":
            raise ValueError("invalid nested trace state")
        saved = data_copy(dict(state))
        if saved.get("max_records") != self.max_records:
            raise ValueError("trace capacity differs from checkpoint")
        if not isinstance(saved.get("records"), list) or len(saved["records"]) > self.max_records:
            raise ValueError("invalid nested trace records")
        self.run_id, self.initial, self.records = saved["run_id"], saved["initial"], saved["records"]
