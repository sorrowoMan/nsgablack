"""Tiny supervised learning problem with an analytical linear solution."""

from __future__ import annotations

import numpy as np

from mlblack.core import Feedback, LearningProblem
from mlblack.pipeline.data_views import as_numeric_data_view


class ClosedFormRegressionProblem(LearningProblem):
    name = "closed_form_linear_regression"
    objective_count = 1

    def __init__(self) -> None:
        x = np.asarray([0.0, 0.25, 0.5, 0.75, 1.0], dtype=float)
        y = 0.2 + 0.7 * x
        self.data = as_numeric_data_view(
            x.reshape(-1, 1),
            y,
            feature_names=("x",),
            target_name="y",
        )

    def training_arrays(self) -> tuple[np.ndarray, np.ndarray]:
        x = self.data.X_train[:, 0]
        design = np.column_stack([np.ones_like(x), x])
        return design, self.data.y_train.copy()

    def evaluate(self, candidate, context=None) -> Feedback:
        del context
        x = self.data.X_train[:, 0]
        prediction = float(candidate["intercept"]) + float(candidate["slope"]) * x
        loss = float(np.mean((prediction - self.data.y_train) ** 2))
        return Feedback(
            objectives=np.asarray([loss], dtype=float),
            loss=loss,
            metrics={"mse": loss},
        )
