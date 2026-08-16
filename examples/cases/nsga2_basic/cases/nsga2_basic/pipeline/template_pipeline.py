# -*- coding: utf-8 -*-
# Pipeline component templates: init/mutate/repair.

from __future__ import annotations

from typing import Optional

import numpy as np

from nsgablack.representation.base import RepresentationComponentContract


class PipelineInitializerTemplate(RepresentationComponentContract):
    # Initializer template.

    context_requires = ()
    context_provides = ()
    context_mutates = ()
    context_cache = ()
    context_notes = ("Initializer template: produce a feasible initial candidate.",)

    def initialize(self, problem, context: Optional[dict] = None) -> np.ndarray:
        _ = context
        return np.zeros(problem.dimension, dtype=float)


class PipelineMutationTemplate(RepresentationComponentContract):
    # Mutation template.

    context_requires = ()
    context_provides = ()
    context_mutates = ()
    context_cache = ()
    context_notes = ("Mutation template: input x -> output x'.",)

    def mutate(self, x: np.ndarray, context: Optional[dict] = None) -> np.ndarray:
        _ = context
        return np.array(x, copy=True)


class PipelineRepairTemplate(RepresentationComponentContract):
    # Repair template.

    context_requires = ()
    context_provides = ()
    context_mutates = ()
    context_cache = ()
    context_notes = ("Repair template: project candidates back to feasibility.",)

    def repair(self, x: np.ndarray, context: Optional[dict] = None) -> np.ndarray:
        _ = context
        return np.array(x, copy=True)
