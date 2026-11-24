"""Encode the fitting specification; fitted weights belong to the model Artifact."""

from __future__ import annotations

import numpy as np

from mlblack.core import ModelRepresentation, UnknownState


class ClosedFormDataPipeline(ModelRepresentation):
    name = "full_batch_closed_form"

    def init(self, context) -> UnknownState:
        del context
        return UnknownState(
            values=np.ones(1, dtype=float),
            metadata={"model_family": "linear", "codec": "linear-fit-spec/v1"},
        )

    def decode(self, state: UnknownState, context=None):
        del context
        return {"fit_intercept": bool(state.as_array()[0] >= 0.5)}

    def encode(self, model, context=None) -> UnknownState:
        del context
        return UnknownState(
            values=np.asarray([float(model["fit_intercept"])], dtype=float),
            metadata={"model_family": "linear", "codec": "linear-fit-spec/v1"},
        )
