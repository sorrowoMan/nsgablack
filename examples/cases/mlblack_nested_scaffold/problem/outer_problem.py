from __future__ import annotations

import numpy as np

from nsgablack.core.base import BlackBoxProblem

from evaluation.inner_mlblack_runner import MlblackFlowRunner


class MlblackNestedOuterProblem(BlackBoxProblem):
    """Outer problem: tune inner mlblack xgboost config via nsgablack."""

    context_requires = ()
    context_provides = ("inner_metrics",)
    context_mutates = ()
    context_cache = ()
    context_notes = ("evaluate(x) delegates to mlblack TrainFlowSpec run.",)

    def __init__(self, inner_runner: MlblackFlowRunner) -> None:
        self.inner_runner = inner_runner
        bounds = {
            "x0": [120.0, 650.0],   # n_estimators
            "x1": [3.0, 10.0],      # max_depth
            "x2": [0.02, 0.2],      # learning_rate
            "x3": [0.6, 1.0],       # subsample
            "x4": [0.6, 1.0],       # colsample_bytree
            "x5": [0.0, 6.0],       # reg_lambda
        }
        super().__init__(
            name="MlblackNestedOuterProblem",
            dimension=6,
            bounds=bounds,
            objectives=["rmse_test", "model_complexity"],
        )
        self.last_inner = None

    def _decode(self, x: np.ndarray) -> dict[str, float | int | str]:
        arr = np.asarray(x, dtype=float).reshape(self.dimension)
        n_estimators = int(np.clip(np.round(arr[0]), 120, 650))
        max_depth = int(np.clip(np.round(arr[1]), 3, 10))
        learning_rate = float(np.clip(arr[2], 0.02, 0.2))
        subsample = float(np.clip(arr[3], 0.6, 1.0))
        colsample_bytree = float(np.clip(arr[4], 0.6, 1.0))
        reg_lambda = float(np.clip(arr[5], 0.0, 6.0))
        return {
            "n_estimators": n_estimators,
            "max_depth": max_depth,
            "learning_rate": learning_rate,
            "subsample": subsample,
            "colsample_bytree": colsample_bytree,
            "reg_alpha": 0.0,
            "reg_lambda": reg_lambda,
            "tree_method": "hist",
            "random_seed": 7,
        }

    def evaluate(self, x: np.ndarray) -> np.ndarray:
        params = self._decode(x)
        inner = self.inner_runner.evaluate_xgboost(params)
        self.last_inner = inner
        complexity = 0.001 * float(params["n_estimators"]) + 0.05 * float(params["max_depth"])
        return np.array([float(inner.rmse), float(complexity)], dtype=float)

    def evaluate_constraints(self, x: np.ndarray) -> np.ndarray:
        _ = x
        return np.zeros(0, dtype=float)
