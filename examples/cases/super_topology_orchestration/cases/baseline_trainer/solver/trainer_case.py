"""Baseline training uses the shared LearningSolver lifecycle and authority."""

from mlblack.integrations import LearningSolver

from ..plugins.artifacts import BaselineArtifacts


class BaselineTrainerCase(LearningSolver):
    def __init__(self, problem, pipeline, adapter, *, resource_context=None,
                 component_overrides=None):
        super().__init__(
            problem=problem, representation=pipeline, adapter=adapter,
            run_name="baseline_trainer", resource_context=resource_context,
            artifact_provider=BaselineArtifacts(),
        )
        self.max_steps = 1
        self.component_override_audit = dict(component_overrides or {})

    def build_summary(self):
        model = self.best_model or {}
        return {
            "case": "baseline_trainer",
            "method": self.semantic_problem.provider.name,
            "weights": [model.get("intercept"), model.get("slope")],
            "loss": None if self.best_feedback is None else self.best_feedback.loss,
            "resource_context": self.resource_context.as_dict(),
            "control_plane": self.control_plane,
            "committed_steps": int(self.generation),
            "evaluation_count": int(self.evaluation_count),
        }

    def build_report(self, raw_result=None):
        return {**super().build_report(raw_result), "summary": self.build_summary()}
