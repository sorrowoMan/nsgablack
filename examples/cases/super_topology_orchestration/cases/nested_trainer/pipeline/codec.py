"""MLBlack codec between an optimization point and a model state."""

from __future__ import annotations

import numpy as np

from mlblack.core import ModelRepresentation, UnknownState


class NestedModelCodec(ModelRepresentation):
    name = "nested-linear-model-codec/v1"

    def init(self, context) -> UnknownState:
        return self.state(
            context.get("outer_candidate", [0.5, 0.5]),
            float(context.get("calibration", 0.0)),
        )

    def decode(self, state: UnknownState, context=None) -> dict[str, float]:
        del context
        capacity, regularization, calibration = state.as_array().reshape(-1)
        return {
            "capacity": float(capacity),
            "regularization": float(regularization),
            "calibration": float(calibration),
        }

    def encode(self, model, context=None) -> UnknownState:
        del context
        return self.state(
            [float(model["capacity"]), float(model["regularization"])],
            float(model["calibration"]),
        )

    def state(self, candidate, calibration: float) -> UnknownState:
        values = np.concatenate(
            [np.asarray(candidate, dtype=float).reshape(-1), [float(calibration)]]
        )
        return UnknownState(
            values=values,
            metadata={
                "codec": self.name,
                "model_family": "synthetic_linear",
                "semantic_fields": ["capacity", "regularization", "calibration"],
            },
        )
