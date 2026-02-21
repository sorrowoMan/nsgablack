"""
Continuous representation helpers.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Any

import numpy as np

from .base import RepresentationComponentContract
from ..utils.context.context_keys import KEY_MUTATION_SIGMA


@dataclass
class UniformInitializer(RepresentationComponentContract):
    low: float = 0.0
    high: float = 1.0
    context_requires = ()
    context_provides = ()
    context_mutates = ()
    context_cache = ()
    context_notes = ("Uniform initializer uses constructor bounds only; no context I/O.",)

    def __post_init__(self) -> None:
        self._rng = np.random.default_rng()

    def initialize(self, problem: Any, context: Optional[dict] = None) -> np.ndarray:
        return self._rng.uniform(self.low, self.high, problem.dimension)


@dataclass
class GaussianMutation(RepresentationComponentContract):
    sigma: float = 0.1
    low: Optional[float] = None
    high: Optional[float] = None
    context_requires = ()
    context_provides = ()
    context_mutates = ()
    context_cache = ()
    context_notes = ("Gaussian mutation uses local sigma/bounds; no context I/O.",)

    def __post_init__(self) -> None:
        self._rng = np.random.default_rng()

    def mutate(self, x: np.ndarray, context: Optional[dict] = None) -> np.ndarray:
        mutated = x + self._rng.normal(0.0, self.sigma, size=x.shape)
        if self.low is not None and self.high is not None:
            mutated = np.clip(mutated, self.low, self.high)
        return mutated


@dataclass
class ContextGaussianMutation(RepresentationComponentContract):
    """Gaussian mutation with sigma optionally controlled by context.

    This is useful for algorithms that vary neighborhood scale (e.g., VNS),
    without hard-coding the operator logic inside the algorithm adapter.
    """

    base_sigma: float = 0.1
    sigma_key: str = KEY_MUTATION_SIGMA
    low: Optional[float] = None
    high: Optional[float] = None
    context_requires = (KEY_MUTATION_SIGMA,)
    context_provides = ()
    context_mutates = ()
    context_cache = ()
    context_notes = (
        "Reads mutation sigma from context; used by adaptive/VNS/SA style adapters.",
    )

    def __post_init__(self) -> None:
        self._rng = np.random.default_rng()

    def mutate(self, x: np.ndarray, context: Optional[dict] = None) -> np.ndarray:
        sigma = float(self.base_sigma)
        if context is not None and self.sigma_key in context:
            try:
                sigma = float(context[self.sigma_key])
            except Exception:
                sigma = float(self.base_sigma)
        mutated = x + self._rng.normal(0.0, sigma, size=x.shape)
        if self.low is not None and self.high is not None:
            mutated = np.clip(mutated, self.low, self.high)
        return mutated


@dataclass
class ClipRepair(RepresentationComponentContract):
    low: float = 0.0
    high: float = 1.0
    context_requires = ()
    context_provides = ()
    context_mutates = ()
    context_cache = ()
    context_notes = ("Clip projection only; no context I/O.",)

    def repair(self, x: np.ndarray, context: Optional[dict] = None) -> np.ndarray:
        return np.clip(x, self.low, self.high)


def _project_to_simplex(v: np.ndarray, z: float = 1.0) -> np.ndarray:
    """Project v onto the simplex {x >= 0, sum(x) = z}."""
    v = np.asarray(v, dtype=float).ravel()
    if z <= 0:
        return np.zeros_like(v)
    if v.size == 0:
        return v
    u = np.sort(v)[::-1]
    cssv = np.cumsum(u)
    rho = np.nonzero(u * np.arange(1, v.size + 1) > (cssv - z))[0]
    if rho.size == 0:
        theta = 0.0
    else:
        rho = rho[-1]
        theta = (cssv[rho] - z) / float(rho + 1)
    w = np.maximum(v - theta, 0.0)
    return w


@dataclass
class ProjectionRepair(RepresentationComponentContract):
    """
    Generic projection-based repair.

    Use cases:
    - bounds projection (clip)
    - simplex projection (sum constraint)
    - custom projection function
    """

    projection: Optional[Any] = None
    low: Optional[float] = None
    high: Optional[float] = None
    sum_target: Optional[float] = None
    cap: Optional[float] = None
    nonnegative: bool = True
    context_requires = ()
    context_provides = ()
    context_mutates = ()
    context_cache = ()
    context_notes = ("Projection is driven by constructor/config values; no context I/O by default.",)

    def repair(self, x: np.ndarray, context: Optional[dict] = None) -> np.ndarray:
        if self.projection is not None:
            return np.asarray(self.projection(x, context), dtype=float)

        arr = np.asarray(x, dtype=float)

        if self.sum_target is not None or self.cap is not None:
            z = float(self.sum_target if self.sum_target is not None else self.cap or 0.0)
            if self.nonnegative:
                arr = np.maximum(arr, 0.0)
            arr = _project_to_simplex(arr, z=z)
        else:
            if self.low is not None and self.high is not None:
                arr = np.clip(arr, self.low, self.high)

        if self.low is not None:
            arr = np.maximum(arr, self.low)
        if self.high is not None:
            arr = np.minimum(arr, self.high)
        return arr
