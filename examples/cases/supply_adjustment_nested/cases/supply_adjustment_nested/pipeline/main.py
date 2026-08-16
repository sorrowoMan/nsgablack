"""Canonical candidate pipeline for nested supply adjustment."""

from .l0_binary_pipeline import build_l0_binary_pipeline

from nsgablack.representation.base import RepresentationPipeline
from nsgablack.representation.integer import IntegerInitializer, IntegerMutation, IntegerRepair


def build_pipeline(problem, *, mutation_sigma: float = 1.0, **_kwargs) -> RepresentationPipeline:
    """Build the L1 event-shift pipeline using per-event problem bounds."""

    if int(getattr(problem, "dimension", 0)) < 0:
        raise ValueError("problem.dimension must be non-negative")
    return RepresentationPipeline(
        initializer=IntegerInitializer(),
        mutator=IntegerMutation(sigma=float(mutation_sigma)),
        repair=IntegerRepair(),
    )


__all__ = ["build_l0_binary_pipeline", "build_pipeline"]
