"""Nested ML semantics projected through the formal LearningSolver lifecycle."""

from mlblack.integrations import LearningSolver

from ..plugins.artifacts import NestedTrainingArtifacts


class NestedTrainerCase(LearningSolver):
    def __init__(self, problem, pipeline, adapter, *, resource_context=None,
                 component_overrides=None):
        super().__init__(
            problem=problem, representation=pipeline, adapter=adapter,
            run_name="nested_trainer", resource_context=resource_context,
            artifact_provider=NestedTrainingArtifacts(),
        )
        self.max_steps = 1
        self.component_override_audit = dict(component_overrides or {})

    def set_case_runtime(self, runtime):
        super().set_case_runtime(runtime)
        self.semantic_problem.case_runtime = runtime
        return self

    def build_summary(self):
        feedback = self.best_feedback
        nested_audit = {} if feedback is None else dict(feedback.info.get("nested_audit", {}))
        if self.best_state is not None:
            nested_audit["model_spec_fingerprint"] = self.model_representation.fingerprint(self.best_state)
        return {
            "case": "nested_trainer",
            "outer_candidate": self.semantic_problem.outer_candidate.tolist(),
            "model": self.best_model,
            "objectives": None if feedback is None else feedback.objectives.tolist(),
            "nested_audit": nested_audit,
            "control_plane": self.control_plane,
            "committed_steps": int(self.generation),
            "evaluation_count": int(self.evaluation_count),
        }

    def build_report(self, raw_result=None):
        summary = self.build_summary()
        return {
            **super().build_report(raw_result),
            "summary": summary,
            "nested_audit": summary["nested_audit"],
        }
