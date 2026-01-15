"""Template for a surrogate control bias."""
from __future__ import annotations

from .base import SurrogateControlBias


class ExampleSurrogateBias(SurrogateControlBias):
    """Template surrogate bias that switches configs by progress."""

    def __init__(self, name: str = "example_surrogate_bias"):
        super().__init__(name=name)

    def apply(self, context):
        if getattr(context, "progress", 0.0) < 0.3:
            return {"prefilter": {"enabled": True, "ratio": 1.0}}
        return {"surrogate_eval": {"enabled": True, "ratio": 0.7}}
