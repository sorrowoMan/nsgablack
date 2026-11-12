"""只读统计已提交步骤的内层调用数；真实成本不随外层失败回滚。"""
import json
from pathlib import Path
from blackbase.participation import ParticipationContract
from nsgablack.plugins.base import Plugin
from nsgablack.utils.engineering.file_io import atomic_write_text

class NestedTracePlugin(Plugin):
    participation = ParticipationContract()
    state_recovery_level = "L1"
    state_recovery_notes = "Explicit bounded scalar observations."
    context_requires = ()
    context_provides = ()
    context_mutates = ()
    context_cache = ()
    context_notes = "Reads committed counters and child-call receipts; no context writes."

    def __init__(self, output_dir):
        super().__init__(name="nested_trace")
        self.output_dir = Path(output_dir)
        self.records, self.run_id = [], None

    def on_solver_init(self, solver):
        self.solver = solver
        run_id = str(self.solver.run_session.run_id)
        if self.run_id != run_id:
            self.records = []
        self.run_id = run_id

    def on_generation_committed(self, generation, outcome):
        self.records.append({"generation": int(generation),
            "outer_evaluations": int(self.solver.evaluation_count),
            "inner_calls": len(self.solver.problem.calls)})

    def on_solver_finalized(self, result):
        atomic_write_text(self.output_dir / "trace.json",
            json.dumps(self.get_state(), ensure_ascii=False, indent=2, allow_nan=False))

    def get_state(self):
        return {"schema": "assembly_workbench.nested_trace/v1", "run_id": self.run_id,
                "records": [dict(row) for row in self.records]}

    def set_state(self, state):
        if state.get("schema") != "assembly_workbench.nested_trace/v1":
            raise ValueError("invalid nested trace state")
        self.run_id = state["run_id"]
        self.records = [dict(row) for row in state["records"]]
