"""标准 Case 输入与结果边界；不拥有另一个资源调度器。"""
import json
from dataclasses import replace
from pathlib import Path
from blackbase.project.case_execution import make_transport_safe
from nsgablack.utils.engineering.file_io import atomic_write_text

class ResponseCase:
    def __init__(self, solver, settings, output_dir, *, payload=None):
        self.solver, self.settings = solver, settings
        self.problem, self.adapter = solver.problem, solver.adapter
        self.pipeline = self.representation_pipeline = solver.representation_pipeline
        self.plugin_manager = solver.plugin_manager
        self.evaluation_mediator = solver.evaluation_mediator
        self.resource_context = solver.resource_context
        self.output_dir = Path(output_dir)
        self.case_runtime = None
        self.task_payload = {"target": .5, "source": "builtin"}
        if payload is not None:
            self.set_case_inputs({"inner_task_payload": payload})

    @property
    def resource_binding_audit(self):
        return getattr(self.solver, "resource_binding_audit", {})

    @resource_binding_audit.setter
    def resource_binding_audit(self, value):
        self.solver.resource_binding_audit = value

    def set_resource_context(self, value):
        self.solver.set_resource_context(value)
        self.resource_context = self.solver.resource_context
        return self

    def get_resource_context(self):
        return self.solver.get_resource_context()

    def set_case_runtime(self, runtime):
        self.case_runtime = runtime
        self.solver.set_case_runtime(runtime)
        return self

    def set_case_inputs(self, inputs):
        if set(inputs) != {"inner_task_payload"}:
            raise ValueError("inner_response requires inputs.inner_task_payload")
        payload = dict(inputs["inner_task_payload"])
        if "target" not in payload:
            raise ValueError("inner_task_payload requires target")
        self.problem.set_target(payload["target"])
        self.pipeline.mutator.set_target(self.problem.target)
        self.task_payload = payload

    def run(self):
        return self.solver.run(max_steps=self.settings.steps,
                               max_step_attempts=self.settings.steps + 2)

    def export_case_result(self, raw_output):
        result = self.solver.export_case_result(raw_output)
        state = result.best_solution
        values = state.values if hasattr(state, "values") else state
        summary = make_transport_safe({"schema": "assembly_workbench.inner_response/v1",
            "case": "inner_response", "target": self.problem.target,
            "best_response": float(values[0]),
            "best_objectives": result.best_objectives.tolist(),
            "committed_steps": int(self.solver.generation),
            "evaluation_count": int(self.solver.evaluation_count),
            "pool_id": self.solver.solution_pool.pool_id,
            "task_payload": self.task_payload,
            "identity": None if self.case_runtime is None else self.case_runtime.identity.as_dict(),
            "resource_grant": dict(self.resource_context.grant),
            "resource_binding_current": bool(dict(self.resource_binding_audit or {}).get("current", False)),
            "artifact_source": "standalone" if self.case_runtime is None else "project_authority"},
            path="inner_response.summary")
        refs = dict(result.artifact_refs)
        if self.case_runtime is not None:
            # Solver lifecycle has ended; the enclosing CaseExecutor still
            # owns its final result serialization and authority seal.
            refs["summary"] = self.case_runtime.publish_artifact("summary", summary, serializer="json",
                kind="conditional-response", metadata={"schema": summary["schema"]})
        atomic_write_text(self.output_dir / "summary.json",
            json.dumps(summary, ensure_ascii=False, indent=2, allow_nan=False))
        return replace(result, artifact_refs=refs, metadata={**dict(result.metadata), "summary": summary})
