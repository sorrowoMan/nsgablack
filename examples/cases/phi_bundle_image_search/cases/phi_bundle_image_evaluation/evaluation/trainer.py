from __future__ import annotations

import numpy as np

from blackbase.resources import ResourceContext
from blackbase.types import Feedback, TrainerResult, UnknownState

from pipeline.main import evaluate_bundle


class PhiBundleEvaluationCase:
    def __init__(self, *, config, bundle, label, resource_context=None):
        self.config = dict(config)
        self.bundle = dict(bundle)
        self.label = str(label)
        self.resource_context = ResourceContext.from_mapping(resource_context)

    def set_resource_context(self, resource_context) -> None:
        self.resource_context = ResourceContext.from_mapping(resource_context)

    def fit(self) -> TrainerResult:
        result = evaluate_bundle(self.bundle, self.config)
        objectives = np.asarray(result["objectives"], dtype=float)
        metrics = dict(result["metrics"])
        summary = {
            **result,
            "label": self.label,
            "resource_context": self.resource_context.as_dict(),
            "status": "ok",
        }
        return TrainerResult(
            best_model=dict(result["model"]),
            best_state=UnknownState(
                values=objectives,
                metadata={
                    "bundle_kind": self.bundle.get("bundle_kind", ""),
                    "selected_features": result["representation_report"].get(
                        "selected_feature_names", ()
                    ),
                },
            ),
            best_objectives=objectives,
            best_feedback=Feedback(
                objectives=objectives,
                loss=float(objectives[0]),
                metrics=metrics,
            ),
            report={"summary": summary},
            metadata={"framework": "mlblack", "semantic_role": "representation_evaluation"},
        )


__all__ = ["PhiBundleEvaluationCase"]
