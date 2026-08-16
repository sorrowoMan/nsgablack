# -*- coding: utf-8 -*-
"""Pipeline helper for the residual boosting recipe vector."""

from __future__ import annotations

from nsgablack.representation import (
    ClipRepair,
    GaussianMutation,
    RepresentationPipeline,
    UniformInitializer,
)


def build_pipeline() -> RepresentationPipeline:
    pipeline = RepresentationPipeline(
        initializer=UniformInitializer(low=[0.0, 0.0, 0.0, 0.0], high=[0.8, 0.8, 1.5, 1.0]),
        mutator=GaussianMutation(sigma=0.12, low=[0.0, 0.0, 0.0, 0.0], high=[0.8, 0.8, 1.5, 1.0]),
        repair=ClipRepair(low=[0.0, 0.0, 0.0, 0.0], high=[0.8, 0.8, 1.5, 1.0]),
        encoder=None,
    )
    pipeline.context_requires = ()
    pipeline.context_provides = ()
    pipeline.context_mutates = ()
    pipeline.context_cache = ()
    pipeline.context_notes = "No context read/write in this minimal pipeline."
    return pipeline
