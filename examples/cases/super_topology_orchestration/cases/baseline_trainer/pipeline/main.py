"""Data schedule/pipeline boundary for the baseline Trainer."""

from __future__ import annotations

import numpy as np

from mlblack.core import ModelRepresentation, UnknownState


class ClosedFormDataPipeline(ModelRepresentation):
    name = "full_batch_closed_form"

    def prepare(self, problem):
        return problem.training_arrays()

    def init(self, context) -> UnknownState:
        del context
        return UnknownState(
            values=np.zeros(2, dtype=float),
            metadata={"model_family": "linear", "codec": "linear-point/v1"},
        )

    def decode(self, state: UnknownState, context=None):
        del context
        intercept, slope = state.as_array().reshape(-1)
        return {"intercept": float(intercept), "slope": float(slope)}

    def encode(self, model, context=None) -> UnknownState:
        del context
        return UnknownState(
            values=np.asarray([model["intercept"], model["slope"]], dtype=float),
            metadata={"model_family": "linear", "codec": "linear-point/v1"},
        )
