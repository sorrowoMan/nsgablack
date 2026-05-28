# -*- coding: utf-8 -*-
"""Classification operating-point calibration case."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

import numpy as np

from mlblack.core import UnknownState
from mlblack.models import LinearPointModel
from mlblack.pipeline.data_views import NumericDataView, train_valid_split
from mlblack.problems import SupervisedClassificationProblem

from nsgablack.core.base import BlackBoxProblem


@dataclass(frozen=True)
class ClassificationCalibrationRecipe:
    threshold: float
    temperature: float


@dataclass(frozen=True)
class OperatingPointProbabilityModel:
    logit_model: LinearPointModel
    threshold: float
    temperature: float
    classes_: tuple[int, int] = (0, 1)
    metadata: Mapping[str, Any] | None = None

    def decision_function(self, X: np.ndarray) -> np.ndarray:
        logits = np.asarray(self.logit_model.predict(X), dtype=float).reshape(-1)
        p_threshold = float(np.clip(self.threshold, 1e-6, 1.0 - 1e-6))
        shift = np.log(p_threshold / (1.0 - p_threshold))
        return logits / max(float(self.temperature), 1e-12) - shift

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        logits = self.decision_function(X)
        p1 = 1.0 / (1.0 + np.exp(-np.clip(logits, -60.0, 60.0)))
        return np.column_stack([1.0 - p1, p1])

    def predict(self, X: np.ndarray) -> np.ndarray:
        idx = np.argmax(self.predict_proba(X), axis=1)
        return np.asarray([self.classes_[int(i)] for i in idx])

    def describe(self) -> dict[str, Any]:
        return {
            "name": "operating_point_probability_model",
            "threshold": float(self.threshold),
            "temperature": float(self.temperature),
            "classes": list(self.classes_),
            "metadata": dict(self.metadata or {}),
        }


class ClassificationThresholdCalibrationProblem(BlackBoxProblem):
    def __init__(self, n_samples: int = 240, valid_ratio: float = 0.3, seed: int = 13) -> None:
        self.data = _build_classification_data(n_samples=int(n_samples), valid_ratio=float(valid_ratio), seed=int(seed))
        self.logit_model = _fit_linear_logit(self.data, l2=0.08, metadata={"stage": "fixed_logit"})
        self.last_report: dict[str, Any] = {}
        self._cache: dict[tuple[float, ...], np.ndarray] = {}
        self._report_cache: dict[tuple[float, ...], dict[str, Any]] = {}
        super().__init__(
            name="ClassificationThresholdCalibrationProblem",
            dimension=2,
            bounds={
                "x0": [0.05, 0.95],
                "x1": [0.35, 3.0],
            },
            objectives=["valid_log_loss", "f1_loss", "intervention_rate"],
        )

    def decode_recipe(self, x: np.ndarray) -> ClassificationCalibrationRecipe:
        arr = np.asarray(x, dtype=float).reshape(-1)
        if arr.size != self.dimension:
            raise ValueError(f"expected {self.dimension} calibration values, got {arr.size}")
        return ClassificationCalibrationRecipe(
            threshold=float(np.clip(arr[0], 0.05, 0.95)),
            temperature=float(np.clip(arr[1], 0.35, 3.0)),
        )

    def evaluate(self, x: np.ndarray) -> np.ndarray:
        arr = np.asarray(x, dtype=float).reshape(-1)
        key = tuple(np.round(arr, 6))
        cached = self._cache.get(key)
        if cached is not None:
            report = self._report_cache.get(key)
            if report is not None:
                self.last_report = dict(report)
            return cached.copy()
        recipe = self.decode_recipe(arr)
        model = OperatingPointProbabilityModel(
            logit_model=self.logit_model,
            threshold=recipe.threshold,
            temperature=recipe.temperature,
            classes_=(0, 1),
            metadata={"owner": "mlblack", "recipe": recipe.__dict__},
        )
        problem = SupervisedClassificationProblem(
            self.data,
            objective_metrics=("log_loss", "f1"),
            positive_label=1,
        )
        feedback = problem.evaluate(
            model,
            UnknownState(values=arr, metadata={"recipe": recipe.__dict__}),
            {},
        )
        X_eval = self.data.X_valid if self.data.X_valid is not None else self.data.X_train
        pred = np.asarray(model.predict(X_eval)).reshape(-1)
        intervention_rate = float(np.mean(pred == 1))
        metrics = dict(feedback.metrics)
        valid_log_loss = float(metrics.get("valid.log_loss", feedback.objectives[0]))
        valid_f1 = float(metrics.get("valid.f1", 1.0 - feedback.objectives[1]))
        f1_loss = 1.0 - valid_f1
        objectives = np.asarray([valid_log_loss, f1_loss, intervention_rate], dtype=float)
        report = {
            "recipe": recipe.__dict__,
            "valid_log_loss": valid_log_loss,
            "valid_f1": valid_f1,
            "valid_accuracy": float(metrics.get("valid.accuracy", 0.0)),
            "valid_precision": float(metrics.get("valid.precision", 0.0)),
            "valid_recall": float(metrics.get("valid.recall", 0.0)),
            "intervention_rate": intervention_rate,
            "mlblack_problem": problem.describe(),
            "model": model.describe(),
        }
        self.last_report = report
        self._report_cache[key] = dict(report)
        self._cache[key] = objectives.copy()
        return objectives

    def evaluate_constraints(self, x: np.ndarray) -> np.ndarray:
        _ = x
        return np.zeros(0, dtype=float)


ExampleProblem = ClassificationThresholdCalibrationProblem


def _build_classification_data(*, n_samples: int, valid_ratio: float, seed: int) -> NumericDataView:
    rng = np.random.default_rng(int(seed))
    X = rng.normal(0.0, 1.0, size=(int(n_samples), 4))
    latent = -0.85 + 1.25 * X[:, 0] - 0.9 * X[:, 1] + 0.65 * X[:, 2] * X[:, 3] + 0.35 * np.sin(1.7 * X[:, 0])
    proba = 1.0 / (1.0 + np.exp(-latent))
    y = (rng.uniform(0.0, 1.0, size=int(n_samples)) < proba).astype(int)
    return train_valid_split(
        X,
        y,
        valid_ratio=float(valid_ratio),
        seed=int(seed),
        feature_names=("x0", "x1", "x2", "x3"),
        target_name="synthetic_binary_label",
    )


def _fit_linear_logit(data: NumericDataView, *, l2: float, metadata: Mapping[str, Any]) -> LinearPointModel:
    X = np.asarray(data.X_train, dtype=float)
    y = np.asarray(data.y_train, dtype=float).reshape(-1)
    target = np.where(y > 0, 1.0, -1.0)
    design = np.column_stack([np.ones(X.shape[0]), X])
    penalty = np.eye(design.shape[1], dtype=float) * float(l2)
    penalty[0, 0] = 0.0
    lhs = design.T @ design + penalty
    rhs = design.T @ target
    try:
        beta = np.linalg.solve(lhs, rhs)
    except np.linalg.LinAlgError:
        beta = np.linalg.pinv(lhs) @ rhs
    return LinearPointModel(
        intercept=float(beta[0]),
        weights=np.asarray(beta[1:], dtype=float),
        feature_names=data.effective_feature_names,
        metadata=dict(metadata),
    )
