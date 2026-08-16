"""Candidate helper utilities."""

from __future__ import annotations

from typing import Any, Mapping, Optional

import numpy as np


def _bounds_array(bounds: Any, dimension: int) -> np.ndarray:
    if isinstance(bounds, Mapping):
        values = list(bounds.values())
    else:
        values = bounds
    arr = np.asarray(values, dtype=float)
    if arr.ndim != 2 or arr.shape[1] != 2:
        raise ValueError("bounds must have shape (dimension, 2)")
    if int(arr.shape[0]) != int(dimension):
        raise ValueError(f"bounds dimension mismatch: {arr.shape[0]} != {dimension}")
    return arr


def sample_random_candidate(
    problem: Any,
    *,
    var_bounds: Any = None,
    dimension: Optional[int] = None,
    rng: Any = None,
    context: Optional[Mapping[str, Any]] = None,
) -> np.ndarray:
    """Sample a random candidate from problem bounds."""
    sample = getattr(problem, "sample", None)
    if callable(sample):
        try:
            return np.asarray(sample(), dtype=float).reshape(-1)
        except TypeError:
            return np.asarray(sample(context=context), dtype=float).reshape(-1)

    dim = int(dimension if dimension is not None else getattr(problem, "dimension", 0) or 0)
    bounds = var_bounds if var_bounds is not None else getattr(problem, "bounds", None)
    if bounds is not None and dim > 0:
        arr = _bounds_array(bounds, dim)
        generator = rng if rng is not None else np.random.default_rng()
        return np.asarray(generator.uniform(arr[:, 0], arr[:, 1]), dtype=float).reshape(-1)
    if dim <= 0:
        return np.zeros(0, dtype=float)
    generator = rng if rng is not None else np.random.default_rng()
    return np.asarray(generator.uniform(-1.0, 1.0, size=dim), dtype=float).reshape(-1)


__all__ = [
    "sample_random_candidate",
]
