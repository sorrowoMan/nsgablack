"""权威 Artifact 输入、标准嵌套运行和最终结果发布。"""
import json
from dataclasses import replace
from pathlib import Path
from blackbase.project.case_execution import make_transport_safe
from blackbase.resources import ArtifactPublisher
from nsgablack.utils.engineering.file_io import atomic_write_text

class NestedCase:
    def __init__(self, solver, settings, output_dir):
        self.solver, self.settings = solver, settings
        self.problem, self.adapter = solver.problem, solver.adapter
        self.pipeline = self.representation_pipeline = solver.representation_pipeline
        self.plugin_manager = solver.plugin_manager
        self.evaluation_mediator = solver.evaluation_mediator
        self.resource_context = solver.resource_context
        self.output_dir = Path(output_dir)
        self.case_runtime = None
        self.input_artifacts = {}
        self.baselines = {}

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
        self.problem.set_case_runtime(runtime)
        return self

    def set_input_artifacts(self, refs):
        expected = {"hybrid_summary", "directions_summary"}
        if set(refs) != expected:
            raise ValueError("outer_nested requires both upstream summary inputs")
        self.input_artifacts = dict(refs)

    def _load_baselines(self):
        if not self.input_artifacts:
            return {"source": "builtin", "reason": "no upstream Artifacts supplied",
                    "summaries": {}, "bindings": {}}
        summaries, bindings = {}, {}
        for name, binding in self.case_runtime.request.input_artifact_bindings.items():
            receipt = binding.publication
            reader = ArtifactPublisher.from_resource_context(
                self.case_runtime.request.resource_context,
                project_run_id=receipt.project_run_id, case_run_id=receipt.case_run_id)
            summaries[name] = json.loads(reader.read_verified(binding).decode("utf-8"))
            bindings[name] = binding.as_dict()
        return {"source": "authoritative_artifacts", "summaries": summaries, "bindings": bindings}

    def run(self):
        if self.case_runtime is None:
            raise RuntimeError("use run_solver.py or the Project group 'nested' for L0-authorized nesting")
        self.baselines = self._load_baselines()
        return self.solver.run(max_steps=self.settings.steps,
                               max_step_attempts=self.settings.steps + 3)

    def export_case_result(self, raw_output):
        result = self.solver.export_case_result(raw_output)
        summary = {"schema": "assembly_workbench.outer_nested/v1", "case": "outer_nested",
            "best_objectives": result.best_objectives.tolist(),
            "committed_steps": int(self.solver.generation),
            "evaluation_count": int(self.solver.evaluation_count),
            "inner_call_count": len(self.problem.calls),
            "pool_id": self.solver.solution_pool.pool_id,
            "identity": self.case_runtime.identity.as_dict(),
            "resource_grant": dict(self.resource_context.grant),
            "resource_binding_current": bool(dict(self.resource_binding_audit or {}).get("current", False)),
            "baseline_source": self.baselines["source"]}
        report = make_transport_safe({"schema": "assembly_workbench.nested_report/v1", "summary": summary,
            "baseline_inputs": self.baselines, "calls": list(self.problem.calls),
            "semantics": {"kind": "evaluation_delegation",
                "outer_objective": "inner_loss + 0.05 * x**2",
                "baseline_use": "authoritative comparison reports, not shared mutable candidates",
                "pool_isolation": "one separate pool per Case invocation"}}, path="outer_nested.report")
        summary = report["summary"]
        refs = dict(result.artifact_refs)
        for name, value in (("summary", summary), ("nested_report", report)):
            # Enclosing Case publication is sealed after this exporter and
            # result serialization succeed, separately from Solver lifecycle.
            refs[name] = self.case_runtime.publish_artifact(name, value, serializer="json",
                kind="nested-orchestration", metadata={"schema": value["schema"]})
            atomic_write_text(self.output_dir / f"{name}.json",
                json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False))
        return replace(result, artifact_refs=refs,
            metadata={**dict(result.metadata), "summary": summary, "nested_report": report})
