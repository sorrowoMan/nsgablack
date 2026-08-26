"""One-dimensional calibration problem nested inside the Trainer Case."""

from __future__ import annotations

import numpy as np

from nsgablack.core import BlackBoxProblem


class CalibrationProblem(BlackBoxProblem):
    def __init__(self, target: float) -> None:
        self.target = float(target)
        super().__init__(
            name="trainer_calibration",
            dimension=1,
            bounds={"x0": [-1.0, 1.0]},
            objectives=("calibration_error",),
        )

    def evaluate(self, candidate, context=None):
        del context
        value = float(np.asarray(candidate, dtype=float).reshape(-1)[0])
        return np.asarray([(value - self.target) ** 2], dtype=float)
