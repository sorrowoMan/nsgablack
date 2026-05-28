# -*- coding: utf-8 -*-
"""ARIMA order search as black-box optimization.

Candidate is a flat vector [p, d, q] (3 integers representing ARIMA order).
evaluate() rounds to integers, fits statsmodels ARIMA, returns AIC (minimize).
"""

from __future__ import annotations

import numpy as np

from nsgablack.core.base import BlackBoxProblem


class ARIMAOrderProblem(BlackBoxProblem):
    def __init__(
        self,
        series: np.ndarray,
        max_p: int = 5,
        max_d: int = 2,
        max_q: int = 5,
    ) -> None:
        self.series = np.asarray(series, dtype=float)
        self.max_p = int(max_p)
        self.max_d = int(max_d)
        self.max_q = int(max_q)
        self.last_order: tuple[int, int, int] | None = None
        self.last_aic: float | None = None
        super().__init__(
            name="ARIMAOrderProblem",
            dimension=3,
            bounds={
                "x0": [0, self.max_p],
                "x1": [0, self.max_d],
                "x2": [0, self.max_q],
            },
            objectives=["aic"],
        )

    def evaluate(self, x: np.ndarray) -> np.ndarray:
        arr = np.asarray(x, dtype=float).reshape(-1)
        if arr.shape[0] < self.dimension:
            return np.array([1e10], dtype=float)

        p = int(np.clip(round(float(arr[0])), 0, self.max_p))
        d = int(np.clip(round(float(arr[1])), 0, self.max_d))
        q = int(np.clip(round(float(arr[2])), 0, self.max_q))

        import warnings
        from statsmodels.tsa.arima.model import ARIMA

        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            try:
                model = ARIMA(self.series, order=(p, d, q))
                fit = model.fit()
                aic = float(fit.aic)
            except Exception:
                aic = 1e10

        self.last_order = (p, d, q)
        self.last_aic = aic
        return np.array([aic], dtype=float)

    def evaluate_constraints(self, x: np.ndarray) -> np.ndarray:
        return np.zeros(0, dtype=float)

    def describe(self) -> dict:
        return {
            "name": self.name,
            "dimension": self.dimension,
            "bounds": {k: list(v) for k, v in self.bounds.items()},
            "max_p": self.max_p,
            "max_d": self.max_d,
            "max_q": self.max_q,
            "series_length": int(len(self.series)),
            "last_order": list(self.last_order) if self.last_order else None,
            "last_aic": self.last_aic,
        }
