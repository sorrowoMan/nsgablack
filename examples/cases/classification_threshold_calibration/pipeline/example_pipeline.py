# -*- coding: utf-8 -*-
"""Pipeline helper for the classification calibration vector."""

from __future__ import annotations

from nsgablack.representation import (
    ClipRepair,
    GaussianMutation,
    RepresentationPipeline,
    UniformInitializer,
)


def build_pipeline() -> RepresentationPipeline:
    pipeline = RepresentationPipeline(
        initializer=UniformInitializer(low=[0.05, 0.35], high=[0.95, 3.0]),
        mutator=GaussianMutation(sigma=0.12, low=[0.05, 0.35], high=[0.95, 3.0]),
        repair=ClipRepair(low=[0.05, 0.35], high=[0.95, 3.0]),
        encoder=None,
    )
    pipeline.context_requires = ()
    pipeline.context_provides = ()
    pipeline.context_mutates = ()
    pipeline.context_cache = ()
    pipeline.context_notes = "No context read/write in this calibration pipeline."
    return pipeline
