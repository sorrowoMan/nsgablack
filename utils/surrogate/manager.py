from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict

import numpy as np

from .trainer import SurrogateTrainer, ModelType


@dataclass
class SurrogateManager:
    models: Dict[str, SurrogateTrainer] = field(default_factory=dict)

    def add_model(self, name: str, model_type: ModelType = "knn") -> SurrogateTrainer:
        trainer = SurrogateTrainer(model_type=model_type)
        self.models[name] = trainer
        return trainer

    def train_model(self, name: str, X: np.ndarray, y: np.ndarray) -> None:
        if name not in self.models:
            raise KeyError(f"Unknown surrogate model: {name}")
        self.models[name].train(X, y)

    def predict_model(self, name: str, X: np.ndarray) -> np.ndarray:
        if name not in self.models:
            raise KeyError(f"Unknown surrogate model: {name}")
        return self.models[name].predict(X)

    def uncertainty(self, name: str, X: np.ndarray) -> np.ndarray:
        if name not in self.models:
            raise KeyError(f"Unknown surrogate model: {name}")
        return self.models[name].predict_uncertainty(X)

