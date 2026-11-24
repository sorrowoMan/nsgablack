"""只读核对真实GA分区和同次选择副结果；不控制算法，不额外求值。"""
from collections.abc import Mapping
import json
import numpy as np

from nsgablack.adapters import partition
from nsgablack.adapters.change_pool import ChangePool
from nsgablack.core.state.solution_pool import SolutionRef
from workflow_trace import WorkflowTrace, json_value, workflow_worker
from ..adapter.workflow import choose_twenty


class PartitionTrace(WorkflowTrace):
    def __init__(self, *, max_steps, working_pool=None):
        super().__init__(case_name="ga_partition", max_steps=max_steps)
        self.previous_members, self.previous_accepted_count, self.partitions = (), 0, []
        self.working_pool = working_pool

    def _observe(self):
        result = super()._observe()
        if self.working_pool is not None:
            pool = self.solver.solution_pool
            result["working_pool"] = {"name": self.working_pool,
                "descriptor": pool.subpool_descriptor(self.working_pool),
                "refs": [ref.as_dict() for ref in pool.subpool_refs(self.working_pool)]}
        return result

    def on_solver_init(self, solver):
        fresh = self.run_id != solver.run_session.run_id
        if fresh:
            self.previous_members, self.previous_accepted_count, self.partitions = (), 0, []
        super().on_solver_init(solver)
        if fresh:
            self.initial["selection_outputs_before"] = {
                name: solver.solution_pool.has_subpool(name) for name in ("elite", "reserve")}

    def on_generation_committed(self, generation, outcome):
        solver, store = self.solver, self.solver.solution_pool
        leaf = workflow_worker(solver.adapter).inner
        accepted = store.select(stage="accepted")
        incoming = accepted[self.previous_accepted_count:]
        offered_refs = (*self.previous_members, *incoming)
        if len(set(offered_refs)) != len(offered_refs):
            raise ValueError("this bounded Project expects unique offered versions")
        before = (solver.evaluation_count, store.record_count, store.publication_ref())
        # The prior observation contains the actual committed collection, not
        # a new ranking of this step's now-published elite.
        previous_elite = (() if not self.partitions else tuple(SolutionRef.from_dict(ref)
            for ref in self.partitions[-1]["selection_outputs"]["elite"]["refs"]))
        offspring_sources = []
        if self.partitions:
            previous_tokens = {ref.candidate_token for ref in accepted[:self.previous_accepted_count]}
            for child, record in zip(incoming, store.read_provenance(incoming), strict=True):
                metadata = record.get("metadata", {}) if isinstance(record, Mapping) else {}
                parents = tuple(SolutionRef.from_dict(ref) for ref in metadata.get("change_source_refs", ()))
                inputs = tuple(SolutionRef.from_dict(ref) for ref in metadata.get("change_input_refs", ()))
                if (len(parents) != 2 or inputs != parents
                        or not set(parents).issubset(previous_elite)):
                    raise ValueError("GA offspring must use exact parents from the previous committed elite")
                if child.candidate_token in previous_tokens:
                    raise ValueError("GA offspring must derive a new candidate identity")
                offspring_sources.append({"child": child.as_dict(),
                    "source_refs": [ref.as_dict() for ref in parents],
                    "change_input_refs": [ref.as_dict() for ref in inputs]})
        scope = ChangePool(store, allowed_refs=offered_refs, allow_main=False)
        try:
            source = scope.read(offered_refs)
            source_refs, source_values = source.refs, source.values.copy()
            # Replay only the deterministic read operation to validate the
            # already-committed algorithm result; no Problem or RNG is called.
            selected, remaining = partition(source, by=choose_twenty)
            positions = {ref: index for index, ref in enumerate(source_refs)}
            selected_positions = [positions[ref] for ref in selected.refs]
            remaining_positions = [positions[ref] for ref in remaining.refs]
            needed = min(leaf.cfg.population_size, len(source)) - len(selected)
            expected = selected.concat(remaining.take(range(needed)))
            members = tuple(leaf.get_population_solution_refs(solver))
            if members != expected.refs:
                raise ValueError("GA did not apply the exact partition selection positions")
            expected_outputs = {"elite": expected.take(range(len(selected))).refs,
                                "reserve": remaining.take(range(needed, len(remaining))).refs}
            outputs = {}
            for name, refs in expected_outputs.items():
                if not store.has_subpool(name) or store.subpool_refs(name) != refs:
                    raise ValueError(f"named selection output differs from its exact offered positions: {name}")
                outputs[name] = {"refs": [ref.as_dict() for ref in refs],
                    "descriptor": store.subpool_descriptor(name),
                    "positions": [positions[ref] for ref in refs]}
            if (not set(expected_outputs["elite"]).issubset(members)
                    or set(expected_outputs["reserve"]).intersection(members)):
                raise ValueError("elite must come from final members and reserve must remain outside")
            if leaf.get_bound_operator("pool_maintenance") is not None:
                raise ValueError("named selection outputs must not rely on a second maintenance callback")
            if source.refs != source_refs or not np.array_equal(source.values, source_values):
                raise ValueError("partition changed its input Pool")
            if before != (solver.evaluation_count, store.record_count, store.publication_ref()):
                raise ValueError("partition observation changed evaluation or publication state")
            self.partitions.append({
                "step": int(solver.run_progress_steps), "input_count": len(source),
                "selected_count": len(selected), "remaining_count": len(remaining),
                "selected_positions": selected_positions,
                "remaining_positions": remaining_positions,
                "source_refs": [ref.as_dict() for ref in source.refs],
                "selected_refs": [ref.as_dict() for ref in selected.refs],
                "remaining_refs": [ref.as_dict() for ref in remaining.refs],
                "applied_refs": [ref.as_dict() for ref in members],
                "selection_outputs": outputs,
                "previous_elite_refs": [ref.as_dict() for ref in previous_elite],
                "offspring_sources": offspring_sources,
                "parent_read_added_evaluations": 0,
                "elite_from_final_members": True, "maintenance_bound": False,
                "source_unchanged": True, "evaluation_count": int(solver.evaluation_count),
                "partition_added_evaluations": 0,
                "evaluation_budget_reserved": int(solver.evaluation_budget_reserved),
            })
        finally:
            scope.close()
        self.previous_members = members
        self.previous_accepted_count = len(accepted)
        super().on_generation_committed(generation, outcome)

    def get_state(self):
        return {**super().get_state(), "partition_schema": "pool_workflow_pilot.partition_trace/v2",
            "working_pool": self.working_pool,
            "previous_members": [ref.as_dict() for ref in self.previous_members],
            "previous_accepted_count": self.previous_accepted_count,
            "partitions": self.partitions}

    def set_state(self, state):
        if (not isinstance(state, Mapping)
                or state.get("partition_schema") != "pool_workflow_pilot.partition_trace/v2"
                or state.get("working_pool") != self.working_pool
                or not isinstance(state.get("partitions"), list)
                or len(state["partitions"]) > self.max_steps
                or type(state.get("previous_accepted_count")) is not int
                or state["previous_accepted_count"] < 0):
            raise ValueError("invalid partition observation checkpoint")
        previous = tuple(SolutionRef.from_dict(ref) for ref in state["previous_members"])
        saved = json.loads(json.dumps(dict(state), default=json_value))
        super().set_state(saved)
        self.previous_members = previous
        self.previous_accepted_count = saved["previous_accepted_count"]
        self.partitions = saved["partitions"]
