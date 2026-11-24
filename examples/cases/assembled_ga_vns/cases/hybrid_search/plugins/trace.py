"""只观察已提交步骤；最终发布后导出观测 JSON/CSV，不修改搜索或 context。"""
from __future__ import annotations

import csv
import io
import json
from collections.abc import Mapping
from pathlib import Path

from blackbase.participation import ParticipationContract
from nsgablack.plugins.base import Plugin
from nsgablack.core.state.solution_pool import SolutionRef
from nsgablack.utils.engineering.file_io import atomic_write_text


def _data_copy(value):
    """本组件的状态仅含有限 JSON 数据，不复制 Solver/Adapter 对象图。"""
    return json.loads(json.dumps(value, allow_nan=False))


class CommittedTracePlugin(Plugin):
    """小示例的轻量标量轨迹；不持有另一份 Adapter 或候选状态。"""

    participation = ParticipationContract()
    state_recovery_level = "L1"
    state_recovery_notes = "Explicit JSON codec for bounded committed observations."
    context_notes = ("Observes committed state without constructing a Unit.",)

    def __init__(self, *, max_records=128, output_dir=None):
        super().__init__(name="committed_trace")
        if type(max_records) is not int or max_records < 1:
            raise ValueError("max_records must be a positive integer")
        self.max_records = max_records
        self.output_dir = None if output_dir is None else Path(output_dir)
        self.run_id = None
        self.initial = None
        self.records = []
        self.final_summary = None
        self._started = None

    def _observe(self, *, include_operations=False):
        solver = self.solver
        root = solver.adapter
        pool = solver.solution_pool
        units = []
        operations = []

        def visit(adapter, path):
            # 只读取已有 Unit，绝不调用 ensure_unit 或 UnitBuilder。
            structure = getattr(adapter, "algorithm_unit", None)
            current = getattr(adapter, "current_unit", None)
            neighborhood = getattr(adapter, "neighborhood_unit", None)
            members = getattr(structure, "population", None)
            ages = getattr(structure, "member_age", None)
            member_age = [] if ages is None else [int(age) for age in ages]
            views = pool.subpools_created_by(path)
            units.append({
                "path": "/".join(path),
                "type": type(adapter).__name__,
                "structure_exists": structure is not None,
                "current_exists": current is not None,
                "neighborhood_exists": neighborhood is not None,
                "population_members": 0 if members is None else len(members),
                "member_age": member_age,
                "member_age_min": min(member_age, default=None),
                "member_age_max": max(member_age, default=None),
                "published_views": len(views),
                "published_view_members": sum(len(pool.subpool_refs(name)) for name in views),
            })
            if include_operations:
                operations.append({
                    "path": "/".join(path), "type": type(adapter).__name__,
                    "operations": _data_copy(adapter.get_operation_contract()),
                })
            # 正式所有权树；路径规则与 subpools 的实例来源寻址一致。
            for index, child in enumerate(adapter.step_transaction_children()):
                visit(child, (*path, f"{index}:{child.name}"))

        visit(root, (root.name,))
        projection = root.get_runtime_context_projection(solver)
        incumbent = solver.get_incumbent()
        authority = solver.population_authority
        handle = authority.snapshot_handle
        observation = {
            "logical_steps": int(solver.run_progress_steps),
            "evaluations": int(solver.evaluation_count),
            "phase": str(projection.get("phase", "unassigned")),
            "pool_records": int(pool.record_count),
            "pool_sequence": int(pool.timestamp.sequence),
            "authority_generation": authority.snapshot_generation,
            "authority_key": None if handle is None else str(handle.key),
            "best_score": None if incumbent is None else float(incumbent.score),
            "units": units,
        }
        is_plan = hasattr(root, "cursor")
        if is_plan:
            # The committed call's task summaries describe its local label;
            # the cursor may already point at the next stage or round.
            summaries = projection.get("unit_tasks", {})
            phases = {item["phase"] for item in summaries.values()}
            if len(phases) == 1:
                observation["phase"] = next(iter(phases))
            observation["execution_plan"] = {
                "cursor": root.cursor.get_state(),
                "completed": root.cursor.completed,
                "tasks": {unit.role: unit.adapter.task_status for unit in root.units},
            }
        # Optional elite-mode evidence uses public committed Pool reads and
        # the task's formal checkpoint state; it does not control scheduling.
        if pool.has_subpool("ga_elite"):
            refs = pool.subpool_refs("ga_elite")
            raw_f, raw_v = pool.read_raw_feedback(refs)
            ga = root.units[0].adapter.inner
            observation["elite"] = {
                "name": "ga_elite", "descriptor": pool.subpool_descriptor("ga_elite"),
                "refs": [ref.as_dict() for ref in refs],
                "raw_objectives": raw_f.tolist(), "raw_violations": raw_v.tolist()}
            observation["ga_member_refs"] = [ref.as_dict()
                for ref in ga.get_population_solution_refs(solver)]
            request = root.units[1].adapter.task_status["request"]
            if is_plan:
                observation["refinement_request"] = request
            first_refinement = not any(row["phase"] == "vns" and (
                not is_plan or row.get("refinement_request") == request) for row in self.records)
            if observation["phase"] == "vns" and first_refinement:
                task = root.units[1].adapter.get_state()["pool_task"]
                if pool.has_subpool(task["view"]):
                    observation["frozen_refinement_refs"] = [ref.as_dict()
                        for ref in pool.subpool_refs(task["view"])]
            if observation["phase"] == "return":
                aggregate = pool.subpool_refs("ga_vns/refined")
                aggregate_f, aggregate_v = pool.read_raw_feedback(aggregate)
                observation["aggregate_return"] = {
                    "refs": [ref.as_dict() for ref in aggregate],
                    "raw_objectives": aggregate_f.tolist(), "raw_violations": aggregate_v.tolist()}
                if is_plan:
                    selected = root.get_pool_task_results(solver, "vns")
                    observation["selected_return"] = [ref.as_dict() for ref in selected]
                source = next(row["elite"] for row in reversed(self.records) if row["phase"] == "ga")
                source_f, source_v = pool.read_raw_feedback(tuple(
                    SolutionRef.from_dict(ref) for ref in source["refs"]))
                observation["source_raw_unchanged"] = (
                    source_f.tolist() == source["raw_objectives"]
                    and source_v.tolist() == source["raw_violations"])
        if include_operations:
            observation["operation_contracts"] = operations
        return observation

    def on_solver_init(self, solver):
        run_id = solver.run_session.run_id
        if self.run_id != run_id:
            self.records = []
            self.final_summary = None
            self.initial = None
        self.run_id = run_id
        if self.initial is None:
            self.initial = self._observe(include_operations=True)
        self._started = None

    def on_generation_start(self, generation):
        # 该 hook 在提交之后调用，不能当作算法执行前的状态。
        self._started = (int(generation), self._observe())

    def on_generation_committed(self, generation, outcome):
        if not bool(outcome.get("committed", False)):
            raise ValueError("committed hook requires a committed outcome")
        row = self._observe()
        if self._started != (int(generation), row):
            raise RuntimeError("committed lifecycle observations disagree")
        if len(self.records) >= self.max_records:
            raise RuntimeError("example trace capacity exhausted")
        self.records.append({"generation": int(generation), **row})
        self._started = None

    def on_solver_finalized(self, result):
        # 此时结果已发布；不在 finishing 阶段提前宣称成功。
        self.final_summary = self._observe()
        if self.output_dir is None:
            return
        incumbent = self.solver.get_incumbent()
        best = None if incumbent is None else {
            "candidate": incumbent.candidate.tolist(),
            "selection_objectives": incumbent.objectives.tolist(),
            "selection_constraint_violation": float(incumbent.constraint_violation),
            "selection_score": float(incumbent.score),
            "candidate_token": incumbent.candidate_token,
        }
        # 观测文件，不声明为带权威发布收据的 Artifact。
        payload = {**self.get_state(), "final_incumbent": best}
        atomic_write_text(self.output_dir / "trace.json",
                          json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False))
        columns = ("generation", "logical_steps", "evaluations", "phase", "best_score",
                   "pool_records", "pool_sequence", "authority_generation", "authority_key",
                   "ga_structure_exists", "ga_member_age_min", "ga_member_age_max",
                   "vns_current_exists", "vns_neighborhood_exists")
        stream = io.StringIO(newline="")
        writer = csv.DictWriter(stream, fieldnames=columns)
        writer.writeheader()
        for record in self.records:
            row = {key: record[key] for key in columns if key in record}
            units = record["units"]
            row["ga_structure_exists"] = any(unit["type"] == "NSGA2Adapter" and
                                               unit["structure_exists"] for unit in units)
            ga = next((unit for unit in units if unit["type"] == "NSGA2Adapter"), None)
            row["ga_member_age_min"] = None if ga is None else ga["member_age_min"]
            row["ga_member_age_max"] = None if ga is None else ga["member_age_max"]
            row["vns_current_exists"] = any(unit["type"] == "VNSAdapter" and
                                              unit["current_exists"] for unit in units)
            row["vns_neighborhood_exists"] = any(unit["type"] == "VNSAdapter" and
                                                   unit["neighborhood_exists"] for unit in units)
            writer.writerow(row)
        atomic_write_text(self.output_dir / "trace.csv", stream.getvalue())

    def get_state(self):
        return _data_copy({
            "schema": "assembled_ga_vns.committed_trace/v1",
            "max_records": self.max_records,
            "run_id": self.run_id,
            "initial": self.initial,
            "records": self.records,
            "final_summary": self.final_summary,
        })

    def set_state(self, state):
        if not isinstance(state, Mapping):
            raise TypeError("trace state must be a Mapping")
        saved = _data_copy(dict(state))
        if saved.get("schema") != "assembled_ga_vns.committed_trace/v1":
            raise ValueError("unsupported trace state schema")
        if saved.get("max_records") != self.max_records:
            raise ValueError("trace capacity differs from checkpoint")
        records = saved.get("records")
        if not isinstance(records, list) or len(records) > self.max_records:
            raise ValueError("invalid trace records")
        if any(not isinstance(row, dict) or type(row.get("generation")) is not int
               or row["generation"] < 0 for row in records):
            raise ValueError("invalid committed generation record")
        self.run_id = saved["run_id"]
        self.initial = saved["initial"]
        self.records = records
        self.final_summary = saved["final_summary"]
        self._started = None


def build_plugin(*, output_dir=None, max_records=128):
    return CommittedTracePlugin(output_dir=output_dir, max_records=max_records)
