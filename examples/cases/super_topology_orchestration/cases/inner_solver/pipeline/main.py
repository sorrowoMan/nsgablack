"""Candidate pipeline for inner calibration."""

from nsgablack.representation import (
    ClipRepair,
    ContextGaussianMutation,
    RepresentationPipeline,
    UniformInitializer,
)


def build_pipeline() -> RepresentationPipeline:
    return RepresentationPipeline(
        initializer=UniformInitializer(-1.0, 1.0),
        mutator=ContextGaussianMutation(base_sigma=0.15, low=-1.0, high=1.0),
        repair=ClipRepair(-1.0, 1.0),
        random_seed=29,
    )
