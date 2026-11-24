"""观察实际装配与提交；最终发布前只检查一致性，不改变算法。"""
from __future__ import annotations

import json
from pathlib import Path

from blackbase.participation import ParticipationContract
from nsgablack.plugins.base import Plugin
from nsgablack.utils.engineering.file_io import atomic_write_text
from ..problem import recipe_cost


def detached(value):
    return json.loads(json.dumps(value, allow_nan=False))


class WorkbenchTrace(Plugin):
    participation = ParticipationContract(vetoes=("finalization",))
    state_recovery_level = "L1"
    state_recovery_notes = "Restores bounded JSON observations; never copies live components."
    context_notes = "Reads committed Pool/Unit/Authority and validates final publication."

    def __init__(self, output_dir, max_records):
        super().__init__(name="workbench_trace", priority=100)
        self.output_dir, self.max_records = Path(output_dir), max_records
        self.run_id, self.initial, self.final = None, None, None
        self.records, self.components = [], []

    def _tree(self):
        def visit(owner, path):
            yield path, owner
            for index, child in enumerate(owner.step_transaction_children()):
                yield from visit(child, f"{path}/{index}:{child.name}")
        return list(visit(self.solver.adapter, self.solver.adapter.name))

    def _read(self):
        solver, pool = self.solver, self.solver.solution_pool
        owners = self._tree()
        ga = next(item for _path, item in owners if item.name == "ga")
        vns_task = next(unit.adapter for unit in solver.adapter.units if unit.role == "vns")
        unit = ga.algorithm_unit  # 只观察，绝不为了日志调用 ensure_unit。
        refs = () if unit is None else tuple(ga.get_population_solution_refs(solver))
        raw_f, raw_v = pool.read_raw_feedback(refs)
        elite = pool.subpool_refs("elite") if pool.has_subpool("elite") else ()
        refined = (solver.adapter.get_pool_task_results(solver, "vns")
                   if vns_task.task_status["status"] == "done" else ())
        phases = sorted({task["phase"] for task in solver.adapter.get_runtime_context_projection(
            solver).get("unit_tasks", {}).values()})
        identity = solver.get_population_authority_identity()
        repair_component = solver.representation_pipeline.problem_repair
        return {"phase": phases, "evaluations": int(solver.evaluation_count),
            "problem_calls": int(solver.problem.evaluation_count),
            "pool_records": pool.record_count, "pool_sequence": pool.timestamp.sequence,
            "pool_initial_refs": [ref.as_dict() for ref in pool.select(stage="initial")],
            "authority_epoch": None if identity is None else identity.epoch,
            "ga_unit_exists": unit is not None,
            "member_age": [] if unit is None else unit.member_age.tolist(),
            "member_refs": [ref.as_dict() for ref in refs],
            "raw_objectives": raw_f.tolist(), "raw_violations": raw_v.tolist(),
            "selection_objectives": [] if unit is None else unit.objectives.tolist(),
            "elite_refs": [ref.as_dict() for ref in elite],
            "refinement_request": vns_task.task_status["request"],
            "refined_selected_refs": [ref.as_dict() for ref in refined],
            "repair": {"calls": repair_component.calls, "changed": repair_component.changed}}

    def on_solver_init(self, solver):
        run_id = solver.run_session.run_id
        if self.run_id != run_id:
            self.run_id, self.initial, self.final = run_id, None, None
            self.records = []
        self.components = [{"path": path, "type": f"{type(owner).__module__}.{type(owner).__name__}"}
                           for path, owner in self._tree()]
        self.components += [{"path": "plugin", "type": type(plugin).__name__}
                            for plugin in solver.plugin_manager.plugins]
        self.components += [{"path": "evaluation_provider", "type": type(provider).__name__}
                            for provider in solver.evaluation_mediator.list_providers()]
        self.components += [{"path": path, "type": type(owner).__name__} for path, owner in (
            ("problem", solver.problem), ("pipeline", solver.representation_pipeline),
            ("bias", solver.bias_module))]
        if self.initial is None:
            self.initial = self._read()

    def on_generation_committed(self, generation, outcome):
        if len(self.records) >= self.max_records:
            raise ValueError("workbench trace capacity exceeded")
        self.records.append({"generation": int(generation), **self._read()})

    def on_solver_finalization_prepare(self, result):
        solver = self.solver
        authority = solver.get_population_authority_identity()
        if authority is not None and solver.snapshot_store.read_verified(authority.snapshot).data.get(
                "solution_pool_ref") != solver.solution_pool.publication_ref():
            raise ValueError("final authority and Pool manifest disagree")
        incumbent = solver.get_incumbent()
        if incumbent is not None and not solver.problem.is_valid(incumbent.candidate):
            raise ValueError("final recipe is not feasible")
        runtime = getattr(solver, "case_runtime", None)
        if runtime is not None and runtime.artifact_publisher is not None:
            runtime.begin_finalization_transaction("case_finalization").publish("summary", {
                "case": "hybrid_search", "run_id": self.run_id, "steps": solver.run_progress_steps,
                "evaluations": solver.evaluation_count,
                "best_candidate": None if incumbent is None else incumbent.candidate.tolist(),
                "raw_objective_recomputed": None if incumbent is None else float(recipe_cost(incumbent.candidate)),
                "raw_objective_source": "analytical_recomputation_for_report",
                "selection_objectives": None if incumbent is None else incumbent.objectives.tolist(),
                "components": self.components}, serializer="json", kind="workbench-summary")

    def on_solver_finalized(self, result):
        self.final = self._read()
        self.final["checkpoint"] = next(plugin.latest_checkpoint_path
            for plugin in self.solver.plugin_manager.plugins if plugin.name == "checkpoint_resume")
        atomic_write_text(self.output_dir / "trace.json", json.dumps(self.get_state(),
                          ensure_ascii=False, indent=2, allow_nan=False))

    def get_state(self):
        return detached({"schema": "assembly_workbench.hybrid_trace/v1", "run_id": self.run_id,
            "max_records": self.max_records, "components": self.components,
            "initial": self.initial, "records": self.records, "final": self.final})

    def set_state(self, state):
        if (state.get("schema") != "assembly_workbench.hybrid_trace/v1"
                or state.get("max_records") != self.max_records or len(state["records"]) > self.max_records):
            raise ValueError("incompatible hybrid trace state")
        values = detached(state)
        self.run_id, self.initial, self.final = values["run_id"], values["initial"], values["final"]
        self.records, self.components = values["records"], values["components"]
