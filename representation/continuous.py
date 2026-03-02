"""
Continuous representation helpers.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Any, Tuple

import numpy as np

from .base import RepresentationComponentContract
from ..utils.context.context_keys import KEY_BOUNDS, KEY_MUTATION_SIGMA, KEY_PROBLEM


def _as_bound_array(value: Any, size: int) -> Optional[np.ndarray]:
    if value is None:
        return None
    arr = np.asarray(value, dtype=float).reshape(-1)
    if arr.size == 1:
        return np.full(size, float(arr[0]), dtype=float)
    if arr.size != size:
        return None
    return arr


def _resolve_bounds(
    x: np.ndarray,
    context: Optional[dict],
    low: Optional[Any],
    high: Optional[Any],
) -> Optional[Tuple[np.ndarray, np.ndarray]]:
    size = int(np.asarray(x).size)
    low_arr = _as_bound_array(low, size)
    high_arr = _as_bound_array(high, size)
    if low_arr is not None and high_arr is not None:
        lo = np.minimum(low_arr, high_arr)
        hi = np.maximum(low_arr, high_arr)
        return lo, hi

    bounds = None
    if context is not None:
        bounds = context.get(KEY_BOUNDS)
        if bounds is None:
            problem = context.get(KEY_PROBLEM)
            if problem is not None:
                bounds = getattr(problem, "bounds", None)
    if bounds is None:
        return None

    if isinstance(bounds, dict):
        keys = list(bounds.keys())
        if context is not None:
            problem = context.get(KEY_PROBLEM)
            vars_ = getattr(problem, "variables", None) if problem is not None else None
            if isinstance(vars_, (list, tuple)):
                if all(k in bounds for k in vars_):
                    keys = list(vars_)
        pairs = [bounds[k] for k in keys]
    else:
        pairs = list(bounds)

    if len(pairs) != size:
        return None
    low_arr = np.asarray([p[0] for p in pairs], dtype=float)
    high_arr = np.asarray([p[1] for p in pairs], dtype=float)
    lo = np.minimum(low_arr, high_arr)
    hi = np.maximum(low_arr, high_arr)
    return lo, hi


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
class PolynomialMutation(RepresentationComponentContract):
    """Polynomial mutation for bounded continuous variables."""

    eta_m: float = 20.0
    mutation_rate: Optional[float] = None
    low: Optional[float] = None
    high: Optional[float] = None
    context_requires = ()
    context_provides = ()
    context_mutates = ()
    context_cache = ()
    context_notes = ("Polynomial mutation uses bounds (constructor or context).",)

    def __post_init__(self) -> None:
        self._rng = np.random.default_rng()

    def mutate(self, x: np.ndarray, context: Optional[dict] = None) -> np.ndarray:
        arr = np.asarray(x, dtype=float).copy()
        bounds = _resolve_bounds(arr, context, self.low, self.high)
        if bounds is None:
            raise ValueError("PolynomialMutation requires bounds (low/high or context['problem'].bounds).")
        low, high = bounds

        dim = int(arr.size)
        rate = self.mutation_rate
        if rate is None:
            rate = 1.0 / float(max(1, dim))
        mask = self._rng.random(dim) < float(rate)
        if not np.any(mask):
            return arr

        u = self._rng.random(dim)
        eta = max(1e-8, float(self.eta_m))
        delta = np.where(
            u < 0.5,
            (2.0 * u) ** (1.0 / (eta + 1.0)) - 1.0,
            1.0 - (2.0 * (1.0 - u)) ** (1.0 / (eta + 1.0)),
        )
        arr[mask] = arr[mask] + delta[mask] * (high[mask] - low[mask])
        arr = np.clip(arr, low, high)
        return arr


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
class SBXCrossover(RepresentationComponentContract):
    """Simulated Binary Crossover (SBX) for bounded continuous variables."""

    eta_c: float = 15.0
    low: Optional[float] = None
    high: Optional[float] = None
    context_requires = ()
    context_provides = ()
    context_mutates = ()
    context_cache = ()
    context_notes = ("SBX uses bounds (constructor or context).",)

    def __post_init__(self) -> None:
        self._rng = np.random.default_rng()

    def crossover(self, parent1: np.ndarray, parent2: np.ndarray, context: Optional[dict] = None) -> tuple[np.ndarray, np.ndarray]:
        p1 = np.asarray(parent1, dtype=float)
        p2 = np.asarray(parent2, dtype=float)
        u = self._rng.random(p1.shape[0])
        eta = max(1e-8, float(self.eta_c))
        beta = np.where(
            u <= 0.5,
            (2.0 * u) ** (1.0 / (eta + 1.0)),
            (1.0 / (2.0 * (1.0 - u))) ** (1.0 / (eta + 1.0)),
        )
        c1 = 0.5 * ((1.0 + beta) * p1 + (1.0 - beta) * p2)
        c2 = 0.5 * ((1.0 - beta) * p1 + (1.0 + beta) * p2)

        bounds = _resolve_bounds(p1, context, self.low, self.high)
        if bounds is not None:
            low, high = bounds
            c1 = np.clip(c1, low, high)
            c2 = np.clip(c2, low, high)
        return c1, c2


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
