"""Canonical candidate pipeline for nested supply adjustment."""

import math

from .l0_binary_pipeline import build_l0_binary_pipeline

from nsgablack.representation.base import RepresentationPipeline, RepresentationComponentContract
from .event_operators import SupplyEventInitializer, SupplyEventMutation


class SupplyShiftRepair(RepresentationComponentContract):
    context_requires = context_provides = context_mutates = context_cache = ()

    def __init__(self, problem):
        self.problem = problem

    def repair(self, candidate, context=None):
        # The move-count cap is part of the actual candidate meaning, so it
        # must be applied before binding the child task, not only at export.
        return self.problem.decode_shifts(candidate)


class FixedSupplyInitializer(RepresentationComponentContract):
    context_requires = context_provides = context_mutates = context_cache = ()

    def __init__(self, candidate):
        import numpy as np
        self.candidate = np.array(candidate, dtype=float, copy=True)

    def initialize(self, problem, context=None):
        return self.candidate.copy()

    def set_candidate(self, candidate):
        """Replace an unstarted evaluation-only input without exposing writable storage."""
        import numpy as np
        values = np.asarray(candidate, dtype=float)
        if values.ndim != 1 or values.shape != self.candidate.shape or not np.all(np.isfinite(values)):
            raise ValueError("fixed supply candidate must be a finite vector with the configured dimension")
        self.candidate = values.copy()
        return self


def build_pipeline(
    problem, *, local_step_days: int | None = None,
    mutation_sigma: float | None = None, candidate=None, **_kwargs,
) -> RepresentationPipeline:
    """Build per-event search with an explicit integer local_step_days (default 1).

    Half of date edits also resample the event's complete legal day range;
    there is no Gaussian perturbation of every candidate coordinate. The old
    mutation_sigma keyword is only an integer-day alias: fractional values and
    setting both names are rejected instead of silently rounding a sigma.
    """

    if int(getattr(problem, "dimension", 0)) < 0:
        raise ValueError("problem.dimension must be non-negative")
    if mutation_sigma is not None:
        if local_step_days is not None:
            raise ValueError("use local_step_days or its legacy mutation_sigma alias, not both")
        if not math.isfinite(mutation_sigma) or mutation_sigma < 1 or mutation_sigma != int(mutation_sigma):
            raise ValueError("mutation_sigma is now an integer-day alias; use local_step_days >= 1")
        local_step_days = int(mutation_sigma)
    if local_step_days is None:
        local_step_days = 1
    return RepresentationPipeline(
        initializer=SupplyEventInitializer() if candidate is None else FixedSupplyInitializer(candidate),
        mutator=SupplyEventMutation(problem, local_step_days=local_step_days),
        repair=SupplyShiftRepair(problem),
    )


__all__ = ["build_l0_binary_pipeline", "build_pipeline"]
