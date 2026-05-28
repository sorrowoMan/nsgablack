# -*- coding: utf-8 -*-
"""Example pipeline: init + mutate + repair for continuous vectors."""

from __future__ import annotations

from nsgablack.representation import (
    ClipRepair,
    GaussianMutation,
    RepresentationPipeline,
    UniformInitializer,
)


def build_pipeline() -> RepresentationPipeline:
    pipeline = RepresentationPipeline(
        initializer=UniformInitializer(low=-5.0, high=5.0),
        mutator=GaussianMutation(sigma=0.25, low=-5.0, high=5.0),
        repair=ClipRepair(low=-5.0, high=5.0),
        encoder=None,
    )
    pipeline.context_requires = ()
    pipeline.context_provides = ()
    pipeline.context_mutates = ()
    pipeline.context_cache = ()
    pipeline.context_notes = "No context read/write in this minimal pipeline."
    return pipeline
