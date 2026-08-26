"""Closed-form fitting method; no optimizer loop is duplicated here."""

from __future__ import annotations

import numpy as np


class ClosedFormFitMethod:
    name = "linear.least_squares.closed_form"

    def fit(self, design: np.ndarray, target: np.ndarray) -> tuple[np.ndarray, float]:
        weights, *_ = np.linalg.lstsq(design, target, rcond=None)
        residual = design @ weights - target
        return np.asarray(weights, dtype=float), float(np.mean(residual**2))
