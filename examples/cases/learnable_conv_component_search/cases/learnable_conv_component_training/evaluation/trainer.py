from __future__ import annotations

from typing import Any, Mapping

import numpy as np

from blackbase.resources import ResourceContext
from blackbase.types import Feedback, TrainerResult, UnknownState

from pipeline.main import build_features, load_dataset


class LearnableConvTrainingCase:
    """Closed-form ML fit over a candidate convolution representation."""

    def __init__(self, *, config, bundle, label, resource_context=None):
        self.config = dict(config)
        self.bundle = dict(bundle)
        self.label = str(label)
        self.resource_context = ResourceContext.from_mapping(resource_context)

    def set_resource_context(self, resource_context) -> None:
        self.resource_context = ResourceContext.from_mapping(resource_context)

    def fit(self) -> TrainerResult:
        dataset = load_dataset(self.config)
        train_features, pipeline_state = build_features(
            dataset["X_train"], self.bundle
        )
        test_features, _ = build_features(dataset["X_test"], self.bundle)
        y_train = np.asarray(dataset["y_train"], dtype=float).reshape(-1, 1)
        y_test = np.asarray(dataset["y_test"], dtype=float).reshape(-1, 1)
        design = np.column_stack([np.ones(train_features.shape[0]), train_features])
        test_design = np.column_stack([np.ones(test_features.shape[0]), test_features])
        l2 = max(0.0, float(self.config.get("trainer_l2", 0.05)))
        regularizer = np.eye(design.shape[1], dtype=float) * l2
        regularizer[0, 0] = 0.0
        coef = np.linalg.pinv(design.T @ design + regularizer) @ design.T @ y_train
        train_pred = design @ coef
        test_pred = test_design @ coef
        train_rmse = float(np.sqrt(np.mean((train_pred - y_train) ** 2)))
        test_rmse = float(np.sqrt(np.mean((test_pred - y_test) ** 2)))
        metrics = {
            "train_rmse": train_rmse,
            "test_rmse": test_rmse,
            "generalization_gap": test_rmse - train_rmse,
        }
        model = {
            "kind": "ridge_regression",
            "intercept": float(coef[0, 0]),
            "coefficients": coef[1:, 0].tolist(),
            "feature_dim": int(train_features.shape[1]),
        }
        summary = {
            "label": self.label,
            "metrics": metrics,
            "pipeline_state": pipeline_state,
            "pipeline_output_dim": int(train_features.shape[1]),
            "dataset_metadata": dict(dataset["metadata"]),
            "resource_context": self.resource_context.as_dict(),
        }
        feedback = Feedback(
            objectives=np.asarray([test_rmse, max(0.0, test_rmse - train_rmse)]),
            loss=test_rmse,
            metrics=metrics,
        )
        return TrainerResult(
            best_model=model,
            best_state=UnknownState(
                values=np.asarray(self.bundle.get("coefficients", ()), dtype=float),
                metadata={"component_path": self.bundle.get("component_path", "")},
            ),
            best_objectives=feedback.objectives,
            best_feedback=feedback,
            report={"summary": summary},
            metadata={"framework": "mlblack", "trainer_key": "ridge"},
        )


__all__ = ["LearnableConvTrainingCase"]
