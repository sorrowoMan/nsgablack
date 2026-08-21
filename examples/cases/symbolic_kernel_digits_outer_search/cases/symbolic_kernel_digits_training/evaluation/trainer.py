from __future__ import annotations

import numpy as np

from blackbase.resources import ResourceContext
from blackbase.types import Feedback, TrainerResult, UnknownState

from pipeline.main import build_features, load_digits_data


class SymbolicKernelDigitsTrainingCase:
    def __init__(self, *, config, bundle, label, resource_context=None):
        self.config = dict(config)
        self.bundle = dict(bundle)
        self.label = str(label)
        self.resource_context = ResourceContext.from_mapping(resource_context)

    def set_resource_context(self, resource_context) -> None:
        self.resource_context = ResourceContext.from_mapping(resource_context)

    def fit(self) -> TrainerResult:
        if str(self.config.get("trainer_key", "ridge")).lower() != "ridge":
            raise ValueError(
                "symbolic_kernel_digits_training currently exposes the stable "
                "closed-form ridge classifier; select trainer_key='ridge'"
            )
        data = load_digits_data(self.config)
        train_features, pipeline_state = build_features(data["X_train"], self.bundle)
        test_features, _ = build_features(data["X_test"], self.bundle)
        classes = np.asarray(data["classes"], dtype=int)
        y_train = np.asarray(data["y_train"], dtype=int)
        y_test = np.asarray(data["y_test"], dtype=int)
        targets = np.eye(classes.size, dtype=float)[y_train]
        design = np.column_stack([np.ones(train_features.shape[0]), train_features])
        test_design = np.column_stack([np.ones(test_features.shape[0]), test_features])
        l2 = max(0.0, float(self.config.get("trainer_l2", 0.05)))
        regularizer = np.eye(design.shape[1], dtype=float) * l2
        regularizer[0, 0] = 0.0
        coef = np.linalg.pinv(design.T @ design + regularizer) @ design.T @ targets
        train_pred = np.argmax(design @ coef, axis=1)
        test_pred = np.argmax(test_design @ coef, axis=1)
        train_accuracy = float(np.mean(train_pred == y_train))
        test_accuracy = float(np.mean(test_pred == y_test))
        metrics = {
            "train_accuracy": train_accuracy,
            "test_accuracy": test_accuracy,
            "generalization_gap": train_accuracy - test_accuracy,
        }
        model = {
            "kind": "ridge_classifier",
            "classes": classes.tolist(),
            "intercept": coef[0].tolist(),
            "coefficients": coef[1:].tolist(),
            "feature_dim": int(train_features.shape[1]),
        }
        summary = {
            "label": self.label,
            "metrics": metrics,
            "pipeline_state": pipeline_state,
            "pipeline_output_dim": int(train_features.shape[1]),
            "dataset_metadata": dict(data["metadata"]),
            "resource_context": self.resource_context.as_dict(),
        }
        feedback = Feedback(
            objectives=np.asarray([1.0 - test_accuracy, max(0.0, train_accuracy - test_accuracy)]),
            loss=1.0 - test_accuracy,
            metrics=metrics,
        )
        return TrainerResult(
            best_model=model,
            best_state=UnknownState(
                values=np.asarray(
                    self.bundle.get("symbolic_kernel_weights", self.bundle.get("coefficients", ())),
                    dtype=float,
                ),
                metadata={"component_path": self.bundle.get("component_path", "")},
            ),
            best_objectives=feedback.objectives,
            best_feedback=feedback,
            report={"summary": summary},
            metadata={"framework": "mlblack", "trainer_key": "ridge"},
        )


__all__ = ["SymbolicKernelDigitsTrainingCase"]
