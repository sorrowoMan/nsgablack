"""MLBlack codec between an optimization point and a model state."""

from __future__ import annotations

import numpy as np

from mlblack.core import ModelRepresentation, UnknownState


class NestedModelCodec(ModelRepresentation):
    name = "nested-linear-model-spec/v2"

    def __init__(self, outer_candidate=(0.5, 0.5)):
        self.outer_candidate = np.asarray(outer_candidate, dtype=float).reshape(2).copy()

    def init(self, context) -> UnknownState:
        del context
        return self.state(self.outer_candidate)

    def decode(self, state: UnknownState, context=None) -> dict[str, float]:
        del context
        capacity, regularization = state.as_array().reshape(-1)
        return {
            "capacity": float(capacity),
            "regularization": float(regularization),
        }

    def encode(self, model, context=None) -> UnknownState:
        del context
        return self.state(
            [float(model["capacity"]), float(model["regularization"])],
        )

    def state(self, candidate) -> UnknownState:
        values = np.asarray(candidate, dtype=float).reshape(2)
        return UnknownState(
            values=values,
            metadata={
                "codec": self.name,
                "model_family": "synthetic_linear",
                "semantic_fields": ["capacity", "regularization"],
            },
        )
