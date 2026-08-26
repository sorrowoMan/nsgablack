"""A standard ML Trainer Case returning the shared TrainerResult protocol."""

from __future__ import annotations

from typing import Any, Mapping

import numpy as np

from blackbase.resources import ResourceContext
from mlblack.core import TrainerResult


class BaselineTrainerCase:
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
        design, target = self.pipeline.prepare(self.problem)
        weights, _ = self.adapter.fit(design, target)
        model = {"intercept": float(weights[0]), "slope": float(weights[1])}
        state = self.pipeline.encode(model)
        feedback = self.problem.evaluate(model)
        loss = float(feedback.loss)
        summary = {
            "case": "baseline_trainer",
            "method": self.adapter.name,
            "weights": weights.tolist(),
            "loss": loss,
            "resource_context": self.resource_context.as_dict(),
        }
        ref = self.case_runtime.publish_artifact(
            "summary",
            summary,
            kind="ml-baseline",
            metadata={"semantic_owner": "mlblack"},
        )
        return TrainerResult(
            best_model=model,
            best_state=state,
            best_objectives=np.asarray([loss], dtype=float),
            best_feedback=feedback,
            history=({"step": 1, "loss": loss},),
            report={"summary": summary},
            metadata={
                "framework": "mlblack",
                "fit_semantics": "closed_form",
                "problem_type": type(self.problem).__name__,
                "representation_type": type(self.pipeline).__name__,
                "data_view_type": type(self.problem.data).__name__,
            },
            artifact_refs={"summary": ref},
        )
