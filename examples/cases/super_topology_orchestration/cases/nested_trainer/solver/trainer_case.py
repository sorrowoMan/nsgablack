"""Trainer runtime and result projection for the nested ML Case."""

from __future__ import annotations

from typing import Any, Mapping

import numpy as np

from blackbase.resources import ResourceContext
from mlblack.core import TrainerResult


class NestedTrainerCase:
    def __init__(
        self,
        problem,
        pipeline,
        adapter,
        *,
        resource_context=None,
        component_overrides: Mapping[str, Any] | None = None,
    ) -> None:
        self.problem = problem
        self.pipeline = pipeline
        self.representation_pipeline = pipeline
        self.adapter = adapter
        self.resource_context = ResourceContext.from_mapping(resource_context)
        self.component_override_audit = dict(component_overrides or {})
        self.case_runtime = None

    def set_resource_context(self, context):
        self.resource_context = ResourceContext.from_mapping(context)
        return self

    def get_resource_context(self):
        return self.resource_context

    def set_case_runtime(self, runtime):
        self.case_runtime = runtime
        return self

    def fit(self) -> TrainerResult:
        self.case_runtime.checkpoint()
        calibration, child, inner_result = self.adapter.solve_calibration(
            self.case_runtime,
            target=self.problem.calibration_target,
        )
        state = self.pipeline.state(self.problem.outer_candidate, calibration)
        model = self.pipeline.decode(state)
        feedback = self.problem.evaluate(model)
        loss, complexity = np.asarray(feedback.objectives, dtype=float).reshape(-1)
        nested_audit = {
            "trainer_identity": self.case_runtime.identity.as_dict(),
            "inner_identity": child.identity.as_dict(),
            "inner_status": child.status,
            "inner_resource_grant": dict(
                child.request.resource_context.get("grant", {}) or {}
            ),
            "inner_resource_binding_current": bool(
                dict(child.resource_usage.get("binding", {}) or {}).get("current", False)
            ),
            "inner_budget_usage": dict(child.budget_usage),
            "inner_deadline_at": float(child.control.deadline_at),
            "inner_best_objectives": (
                None
                if inner_result.best_objectives is None
                else inner_result.best_objectives.tolist()
            ),
            "model_state_fingerprint": self.pipeline.fingerprint(state),
        }
        summary = {
            "case": "nested_trainer",
            "outer_candidate": self.problem.outer_candidate.tolist(),
            "model": model,
            "objectives": [loss, complexity],
            "nested_audit": nested_audit,
        }
        ref = self.case_runtime.publish_artifact(
            "training_summary",
            summary,
            kind="nested-training-summary",
            metadata={"semantic_owner": "mlblack", "contains_inner_solver": True},
        )
        return TrainerResult(
            best_model=model,
            best_state=state,
            best_objectives=np.asarray([loss, complexity], dtype=float),
            best_feedback=feedback,
            history=({"step": 1, "loss": loss, "complexity": complexity},),
            report={"summary": summary, "nested_audit": nested_audit},
            metadata={
                "framework": "mlblack",
                "problem_type": type(self.problem).__name__,
                "representation_type": type(self.pipeline).__name__,
                "method": self.adapter.name,
                "codec": self.pipeline.name,
            },
            artifact_refs={"training_summary": ref},
        )
