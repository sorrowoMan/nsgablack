"""只读结果观察，不负责拟合、提案或训练数据写入。"""
import json
from pathlib import Path
from blackbase.participation import ParticipationContract
from nsgablack.plugins.base import Plugin


class BOReport(Plugin):
    participation = ParticipationContract(vetoes=("finalization",))
    context_requires = context_provides = context_mutates = context_cache = ()
    context_notes = "Read-only final BO dataset and acquisition report; no shared context keys."

    def __init__(self, output):
        super().__init__(name="bo_report")
        self.output = Path(output)

    def _summary(self):
        solver = self.solver
        unit = solver.adapter.algorithm_unit
        return {"schema": "algorithm_semantics.synchronous_bo/v1",
            "algorithm": "synchronous_bo", "evaluations": solver.evaluation_count,
            "problem_calls": solver.problem.calls, "steps": solver.run_progress_steps,
            "logical_steps": solver.run_progress_steps, "run_id": solver.run_session.run_id,
            "pool_id": solver.solution_pool.pool_id,
            "observations": unit.observations, "model_revision": unit.model_revision,
            "last_acquisition": unit.last_acquisition,
            "raw_best": min(row["y"] for row in unit.observations),
            "resource_binding_current": solver.resource_binding_audit["current"]}

    def on_solver_finalization_prepare(self, result):
        runtime = self.solver.case_runtime
        if runtime is not None:
            runtime.begin_finalization_transaction("case_finalization").publish(
                "summary", self._summary(), serializer="json", kind="case-summary")

    def on_solver_finalized(self, result):
        self.output.mkdir(parents=True, exist_ok=True)
        content = json.dumps(self._summary(), ensure_ascii=False, indent=2, allow_nan=False)
        (self.output / "report.json").write_text(content, encoding="utf-8")
        (self.output / "summary.json").write_text(content, encoding="utf-8")
