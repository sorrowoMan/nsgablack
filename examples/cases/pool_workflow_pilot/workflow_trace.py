"""默认Case与partition分组共用的只读观察，不复制运行器或池实现。"""
from collections.abc import Mapping
import json
from pathlib import Path
from blackbase.participation import ParticipationContract
from nsgablack.adapters import StrategyChainAdapter
from nsgablack.adapters.subpools import adapter_path
from nsgablack.core.state.solution_pool import SolutionRef
from nsgablack.plugins.base import Plugin
from nsgablack.utils.engineering.file_io import atomic_write_text


def json_value(value):
    if hasattr(value, "tolist"):
        return value.tolist()
    if hasattr(value, "as_dict"):
        return value.as_dict()
    raise TypeError(f"unsupported report value: {type(value).__name__}")


def workflow_worker(root):
    """读取本例可选单阶段Chain后的原Router，不创建算法Unit。"""
    while isinstance(root, StrategyChainAdapter):
        children = root.step_transaction_children()
        if len(children) != 1:
            raise ValueError("this demo observer expects one explicit Chain phase")
        root = children[0]
    return root.units[0].adapter


class WorkflowTrace(Plugin):
    participation = ParticipationContract()
    state_recovery_level = "L1"
    state_recovery_notes = "Bounded read-only observations, restored with matching Case and capacity."
    context_notes = ("Never creates Unit, evaluates candidates, or changes pool membership.",)

    def __init__(self, *, case_name, max_steps):
        super().__init__(name="workflow_trace")
        self.case_name, self.max_steps = case_name, int(max_steps)
        self.run_id, self.initial, self.records = None, None, []

    def _observe(self):
        solver, root = self.solver, self.solver.adapter
        worker = workflow_worker(root)
        leaf, pool = worker.inner, solver.solution_pool
        branches = {}
        if root.get_bound_operator("pool_maintenance") is not None:
            from nsgablack.adapters.pool_maintenance import population_member_owners
            for path, owner in population_member_owners(root, root.step_transaction_children()):
                refs = owner.get_population_solution_refs(solver)
                if refs is not None:
                    branches[path] = [ref.as_dict() for ref in refs]
        return {
            "steps": int(solver.run_progress_steps), "evaluations": int(solver.evaluation_count),
            "unit_exists": getattr(leaf, "algorithm_unit", None) is not None,
            "current_exists": getattr(leaf, "current_unit", None) is not None,
            "neighborhood_exists": getattr(leaf, "neighborhood_unit", None) is not None,
            "initial_refs": [ref.as_dict() for ref in pool.select(stage="initial")],
            "accepted_count": len(pool.select(stage="accepted")),
            "members_by_owner": branches,
            "task": worker.task_status, "runtime": leaf.get_runtime_context_projection(solver),
            "published_views": list(pool.subpools_created_by(adapter_path(root, leaf))),
            "elite": {"descriptor": pool.subpool_descriptor("elite"),
                      "refs": [ref.as_dict() for ref in pool.subpool_refs("elite")]},
        }

    def on_solver_init(self, solver):
        if self.run_id != solver.run_session.run_id:
            self.run_id, self.records = solver.run_session.run_id, []
            self.initial = self._observe()

    def on_generation_committed(self, generation, outcome):
        del generation
        if not outcome.get("committed", False) or len(self.records) >= self.max_steps:
            raise ValueError("trace requires a bounded committed generation")
        self.records.append(self._observe())

    def on_solver_finalized(self, result):
        del result
        solver, root, pool = self.solver, self.solver.adapter, self.solver.solution_pool
        leaf = workflow_worker(root).inner
        refs = (leaf.get_population_solution_refs(solver) if self.case_name != "vns_search"
                else leaf.get_pool_refinement_results(solver))
        raw_f, raw_v = pool.read_raw_feedback(refs)
        intake_count = (1 if self.case_name == "vns_search"
                        else int(leaf.cfg.population_size))
        intake_refs = pool.select(stage="accepted")[:intake_count]
        provenance = list(pool.read_provenance(refs))
        for record in provenance:
            for source in record.get("metadata", {}).get("change_input_refs", ()):
                pool.read((SolutionRef.from_dict(source),))
        views = []
        for name in pool.subpools_created_by(adapter_path(root, leaf)):
            views.append({"name": name, "metadata": pool.subpool_metadata(name),
                          "refs": [ref.as_dict() for ref in pool.subpool_refs(name)]})
        output_name = {"moead_search": "moead_trials", "vns_search": "vns_trials",
                       "ga_search": "ga_trials", "ga_partition": "ga_trials"}[self.case_name]
        output_refs = pool.subpool_refs(output_name)
        accepted_refs = pool.select(stage="accepted")
        accepted_f, accepted_v = pool.read_raw_feedback(accepted_refs)
        payload = {**self.get_state(), "final": self._observe(),
            "operation_contract": leaf.get_operation_contract(), "views": views,
            "change_output": {"name": output_name,
                "refs": [ref.as_dict() for ref in output_refs],
                "provenance": list(pool.read_provenance(output_refs))},
            "accepted": {"refs": [ref.as_dict() for ref in accepted_refs],
                         "raw_objectives": accepted_f.tolist(), "raw_violations": accepted_v.tolist()},
            "intake": {"refs": [ref.as_dict() for ref in intake_refs],
                       "provenance": list(pool.read_provenance(intake_refs))},
            "result": {"refs": [ref.as_dict() for ref in refs],
                "candidates": pool.read(refs).numeric_matrix.tolist(),
                "raw_objectives": raw_f.tolist(), "raw_violations": raw_v.tolist(),
                "provenance": provenance}}
        destination = Path(__file__).resolve().parent / "results" / f"{self.case_name}.json"
        atomic_write_text(destination, json.dumps(payload, ensure_ascii=False, indent=2,
                                                  allow_nan=False, default=json_value))

    def get_state(self):
        return {"schema": "pool_workflow_pilot.trace/v3", "case_name": self.case_name,
                "max_steps": self.max_steps, "run_id": self.run_id,
                "initial": self.initial, "records": self.records}

    def set_state(self, state):
        if (not isinstance(state, Mapping) or state.get("schema") != "pool_workflow_pilot.trace/v3"
                or state.get("case_name") != self.case_name or state.get("max_steps") != self.max_steps
                or not isinstance(state.get("records"), list) or len(state["records"]) > self.max_steps):
            raise ValueError("invalid workflow trace checkpoint")
        saved = json.loads(json.dumps(dict(state), default=json_value))
        self.run_id, self.initial, self.records = saved["run_id"], saved["initial"], saved["records"]
