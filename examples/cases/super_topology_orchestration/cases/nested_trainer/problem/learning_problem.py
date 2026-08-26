"""MLBlack learning semantics owned by the nested Trainer."""

from __future__ import annotations

import numpy as np

from mlblack.core import Feedback, LearningProblem


class NestedLearningProblem(LearningProblem):
    name = "synthetic_capacity_regularization_fit"
    objective_count = 2

    def __init__(self, outer_candidate) -> None:
        candidate = np.asarray(outer_candidate, dtype=float).reshape(-1)
        if candidate.shape != (2,):
            raise ValueError("nested Trainer expects a two-dimensional outer candidate")
        self.outer_candidate = candidate.copy()

    @property
    def calibration_target(self) -> float:
        capacity, regularization = self.outer_candidate
        return float(np.clip(0.5 * (capacity - regularization), -1.0, 1.0))

    def score(self, calibration: float) -> tuple[float, float]:
        capacity, regularization = self.outer_candidate
        loss = (
            (float(capacity) - 0.65) ** 2
            + (float(regularization) - 0.25) ** 2
            + 0.2 * (float(calibration) - self.calibration_target) ** 2
        )
        complexity = float(capacity**2 + 0.5 * regularization)
        return float(loss), complexity

    def evaluate(self, candidate, context=None) -> Feedback:
        del context
        calibration = float(candidate["calibration"])
        loss, complexity = self.score(calibration)
        return Feedback(
            objectives=np.asarray([loss, complexity], dtype=float),
            loss=loss,
            metrics={"validation_loss": loss, "complexity": complexity},
        )
