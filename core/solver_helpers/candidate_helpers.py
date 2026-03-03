"""Candidate sampling helpers used by SolverBase."""

from __future__ import annotations

from typing import Any

import numpy as np


def sample_random_candidate(
    *,
    problem: Any,
    var_bounds: Any,
    dimension: int,
    rng: np.random.Generator,
) -> np.ndarray:
    if isinstance(var_bounds, dict):
        var_names = list(getattr(problem, "variables", var_bounds.keys()))
        lows = np.array([var_bounds[name][0] for name in var_names], dtype=float)
        highs = np.array([var_bounds[name][1] for name in var_names], dtype=float)
    else:
        bounds = np.asarray(var_bounds, dtype=float)
        lows = bounds[:, 0]
        highs = bounds[:, 1]
    return rng.uniform(lows, highs, size=dimension)
