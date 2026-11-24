"""Distribution state for positive-weight, full-covariance CMA-ES."""
from dataclasses import dataclass, field
from typing import ClassVar

import numpy as np

from .collections import structure_schema
from .features import FeatureUnit


def validate_distribution(mean, covariance, sigma, path_c, path_sigma, iteration=0):
    """Pure validation, including assembly inspection without allocating a Unit."""
    m, c = np.asarray(mean, dtype=float), np.asarray(covariance, dtype=float)
    if (m.ndim != 1 or not len(m) or c.shape != (len(m), len(m))
            or np.shape(path_c) != m.shape or np.shape(path_sigma) != m.shape):
        raise ValueError("CMA distribution dimensions do not align")
    if (not all(np.all(np.isfinite(v)) for v in (m, c, path_c, path_sigma))
            or not np.isfinite(sigma) or sigma <= 0
            or not np.allclose(c, c.T, rtol=0, atol=1e-12)
            or np.min(np.linalg.eigvalsh(c)) <= 0):
        raise ValueError("CMA distribution must be finite with positive definite covariance")
    if type(iteration) is not int or iteration < 0:
        raise ValueError("CMA iteration must be a nonnegative integer")


@dataclass
class CMAUnit(FeatureUnit):
    unit_id: str
    mean: object = None
    covariance: object = None
    sigma: float = 1.0
    path_c: object = None
    path_sigma: object = None
    iteration: int = 0
    pending: dict = field(default_factory=dict)
    last_cohort: dict = field(default_factory=dict)
    best: dict = field(default_factory=dict)
    schema: ClassVar = structure_schema("cma_distribution", "mean", "covariance", "sigma",
        "path_c", "path_sigma", "iteration", "pending", "last_cohort", "best")

    def validate(self):
        if self.mean is None:
            if any(v is not None for v in (self.covariance, self.path_c, self.path_sigma)):
                raise ValueError("Inactive CMA distribution cannot contain paths or covariance")
            return
        validate_distribution(self.mean, self.covariance, self.sigma,
                              self.path_c, self.path_sigma, self.iteration)
