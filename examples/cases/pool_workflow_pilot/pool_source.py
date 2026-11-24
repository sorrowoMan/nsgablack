"""现有正式启动钩子的薄桥；只预填母池，不建立算法 Unit 或运行搜索。"""
from collections.abc import Mapping
from blackbase.participation import ParticipationContract
from nsgablack.plugins.base import Plugin


class PipelineSource(Plugin):
    participation = ParticipationContract()
    state_recovery_level = "L1"
    state_recovery_notes = "Restores run identity and completed seed flag; never replays a restored source."
    context_notes = ("Calls public init_population; Pipeline owns seed generation.",)

    def __init__(self, count, *, working_pool=None):
        super().__init__(name="pipeline_source")
        if type(count) is not int or count < 1:
            raise ValueError("source count must be a positive integer")
        if working_pool is not None and (not isinstance(working_pool, str) or not working_pool.strip()
                or working_pool in {"reference", "elite", "reserve", "ga_trials"}):
            raise ValueError("working pool requires a distinct nonempty demo collection name")
        self.count, self.run_id, self.seeded = count, None, False
        self.working_pool = working_pool

    def on_solver_init(self, solver):
        run_id = solver.run_session.run_id
        if self.run_id == run_id and self.seeded:
            return
        if solver.run_session.resume_loaded:
            raise ValueError("restored run is missing its completed Pipeline source state")
        self.run_id, self.seeded = run_id, False
        solver.init_population(self.count, solver.build_context())
        # This is a reference collection of initial candidates, not an elite
        # archive. It adds no values or evaluations and is explicit task input.
        solver.solution_pool.create_subpool("reference", solver.solution_pool.select(stage="initial"))
        if self.working_pool is not None:
            # 区域只持有已有种子的精确引用，不复制候选或增加求值。
            solver.solution_pool.create_subpool(self.working_pool,
                                                solver.solution_pool.subpool_refs("reference"))
        # A post-admission function maintains this collection in the step transaction.
        solver.solution_pool.create_subpool("elite")
        self.seeded = True

    def get_state(self):
        return {"schema": "pool_workflow_pilot.source/v4", "count": self.count,
                "run_id": self.run_id, "seeded": self.seeded, "working_pool": self.working_pool}

    def set_state(self, state):
        if (not isinstance(state, Mapping) or state.get("schema") not in {
                "pool_workflow_pilot.source/v3", "pool_workflow_pilot.source/v4"}
                or state.get("count") != self.count or type(state.get("seeded")) is not bool
                or state.get("working_pool") != self.working_pool):
            raise ValueError("invalid Pipeline source checkpoint")
        if state["seeded"] and not isinstance(state.get("run_id"), str):
            raise ValueError("completed Pipeline source requires its run identity")
        self.run_id, self.seeded = state.get("run_id"), state["seeded"]
