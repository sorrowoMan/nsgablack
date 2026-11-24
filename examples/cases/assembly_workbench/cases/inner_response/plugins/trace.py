"""只记录已提交逻辑步；不改变算法或调用额外求值。"""
import json
from pathlib import Path
from blackbase.participation import ParticipationContract
from nsgablack.plugins.base import Plugin
from nsgablack.utils.engineering.file_io import atomic_write_text

class ResponseTracePlugin(Plugin):
    participation = ParticipationContract()
    state_recovery_level = "L1"
    state_recovery_notes = "Explicit bounded scalar observation state."
    context_requires = ()
    context_provides = ()
    context_mutates = ()
    context_cache = ()
    context_notes = "Reads committed counters and writes only a local observation file."

    def __init__(self, output_dir):
        super().__init__(name="response_trace")
        self.output_dir = Path(output_dir)
        self.records = []
        self.run_id = None

    def on_solver_init(self, solver):
        self.solver = solver
        run_id = str(self.solver.run_session.run_id)
        if self.run_id != run_id:
            self.records = []
        self.run_id = run_id

    def on_generation_committed(self, generation, outcome):
        self.records.append({"generation": int(generation),
            "evaluations": int(self.solver.evaluation_count),
            "best_objective": float(self.solver.best_objective)})

    def on_solver_finalized(self, result):
        atomic_write_text(self.output_dir / "trace.json",
            json.dumps(self.get_state(), ensure_ascii=False, indent=2, allow_nan=False))

    def get_state(self):
        return {"schema": "assembly_workbench.response_trace/v1",
                "run_id": self.run_id, "records": [dict(row) for row in self.records]}

    def set_state(self, state):
        if state.get("schema") != "assembly_workbench.response_trace/v1":
            raise ValueError("invalid response trace state")
        self.run_id = state["run_id"]
        self.records = [dict(row) for row in state["records"]]
