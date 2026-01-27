from __future__ import annotations

from dataclasses import dataclass, field
from typing import List

import numpy as np

from .trainer import SurrogateTrainer, ModelType


@dataclass
class VectorSurrogate:
    """Multi-objective vector-output surrogate wrapper.

    - fit: trains one regressor per objective
    - predict: returns shape (N, M)
    - uncertainty: returns shape (N, M)
    """

    num_objectives: int
    model_type: ModelType = "rf"
    trainers: List[SurrogateTrainer] = field(default_factory=list)

    def __post_init__(self) -> None:
        m = int(self.num_objectives)
        if m <= 0:
            raise ValueError("num_objectives must be >= 1")
        if not self.trainers:
            self.trainers = [SurrogateTrainer(model_type=self.model_type) for _ in range(m)]
        if len(self.trainers) != m:
            raise ValueError("trainers length must match num_objectives")

    def fit(self, X: np.ndarray, Y: np.ndarray) -> None:
        X_arr = np.asarray(X, dtype=float)
        Y_arr = np.asarray(Y, dtype=float)
        if Y_arr.ndim == 1:
            Y_arr = Y_arr.reshape(-1, 1)
        if Y_arr.shape[1] != len(self.trainers):
            raise ValueError("Y second dimension must match num_objectives")
        for j, trainer in enumerate(self.trainers):
            trainer.train(X_arr, Y_arr[:, j])

    def predict(self, X: np.ndarray) -> np.ndarray:
        X_arr = np.asarray(X, dtype=float)
        preds = [t.predict(X_arr).reshape(-1) for t in self.trainers]
        return np.stack(preds, axis=1)

    def uncertainty(self, X: np.ndarray) -> np.ndarray:
        X_arr = np.asarray(X, dtype=float)
        u = [t.predict_uncertainty(X_arr).reshape(-1) for t in self.trainers]
        return np.stack(u, axis=1)

