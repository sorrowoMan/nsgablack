from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, Optional

import numpy as np


ModelType = Literal["knn", "rf"]


@dataclass
class SurrogateTrainer:
    model_type: ModelType = "knn"
    model: Optional[Any] = None

    def __post_init__(self) -> None:
        self.model = self._create_model(self.model_type)

    def _create_model(self, model_type: ModelType) -> Any:
        if model_type == "knn":
            from sklearn.neighbors import KNeighborsRegressor

            return KNeighborsRegressor(n_neighbors=5)
        if model_type == "rf":
            from sklearn.ensemble import RandomForestRegressor

            return RandomForestRegressor(n_estimators=200, random_state=42)
        raise ValueError(f"Unsupported model_type: {model_type}")

    def train(self, X: np.ndarray, y: np.ndarray) -> None:
        X_arr = np.asarray(X, dtype=float)
        y_arr = np.asarray(y, dtype=float).ravel()
        if self.model is None:
            self.model = self._create_model(self.model_type)
        self.model.fit(X_arr, y_arr)

    def predict(self, X: np.ndarray) -> np.ndarray:
        if self.model is None:
            raise RuntimeError("Model is not initialized")
        X_arr = np.asarray(X, dtype=float)
        pred = self.model.predict(X_arr)
        return np.asarray(pred, dtype=float)

    def predict_uncertainty(self, X: np.ndarray) -> np.ndarray:
        """Return a simplified uncertainty estimate.

        - KNN: std over neighbor targets (approximation).
        - RF: std over trees.
        """
        X_arr = np.asarray(X, dtype=float)

        if self.model_type == "rf":
            if self.model is None:
                raise RuntimeError("Model is not initialized")
            estimators = getattr(self.model, "estimators_", None)
            if not estimators:
                raise RuntimeError("RandomForestRegressor is not fitted")
            preds = np.stack([tree.predict(X_arr) for tree in estimators], axis=0)
            return np.std(preds, axis=0)

        if self.model_type == "knn":
            if self.model is None:
                raise RuntimeError("Model is not initialized")
            distances, indices = self.model.kneighbors(X_arr, return_distance=True)
            y_train = getattr(self.model, "_y", None)
            if y_train is None:
                raise RuntimeError("KNeighborsRegressor is not fitted")
            neigh_y = np.asarray(y_train)[indices]
            return np.std(neigh_y, axis=1)

        raise ValueError(f"Unsupported model_type: {self.model_type}")

