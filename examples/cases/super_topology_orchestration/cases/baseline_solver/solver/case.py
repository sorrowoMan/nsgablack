"""Case wrapper that adds final Artifact publication to a real Solver."""

from __future__ import annotations

from dataclasses import replace
from typing import Any, Mapping


class BaselineSolverCase:
    def __init__(self, solver, *, component_overrides: Mapping[str, Any] | None = None) -> None:
        self.solver = solver
        self.problem = solver.problem
        self.adapter = solver.adapter
        self.representation_pipeline = solver.representation_pipeline
        self.pipeline = self.representation_pipeline
        self.plugin_manager = solver.plugin_manager
        self.evaluation_mediator = solver.evaluation_mediator
        self.resource_context = solver.resource_context
        self.component_override_audit = dict(component_overrides or {})
        self.case_runtime = None

    def set_resource_context(self, context):
        self.solver.set_resource_context(context)
        self.resource_context = self.solver.resource_context
        return self

    def get_resource_context(self):
        return self.solver.get_resource_context()

    def set_case_runtime(self, runtime):
        self.case_runtime = runtime
        self.solver.set_case_runtime(runtime)
        return self

    def run(self):
        return self.solver.run(max_steps=1, max_step_attempts=3)

    def export_case_result(self, raw_output):
        result = self.solver.export_case_result(raw_output)
        summary = {
            "case": "baseline_solver",
            "best_objectives": (
                None if result.best_objectives is None else result.best_objectives.tolist()
            ),
            "solve_status": result.solve_status,
            "resource_context": self.resource_context.as_dict(),
        }
        ref = self.case_runtime.publish_artifact(
            "summary",
            summary,
            kind="optimization-baseline",
            metadata={"semantic_owner": "nsgablack"},
        )
        return replace(
            result,
            artifact_refs={**dict(result.artifact_refs), "summary": ref},
            metadata={**dict(result.metadata), "baseline": summary},
        )
