import numpy as np

from nsgablack.representation import RepresentationPipeline
from nsgablack.representation.continuous import ClipRepair, UniformInitializer


def build_pipeline(problem):
    low = np.asarray([problem.bounds[f"x{i}"][0] for i in range(problem.dimension)], dtype=float)
    high = np.asarray([problem.bounds[f"x{i}"][1] for i in range(problem.dimension)], dtype=float)
    return RepresentationPipeline(
        initializer=UniformInitializer(low=low, high=high),
        repair=ClipRepair(low=low, high=high),
    )


__all__ = ["build_pipeline"]
