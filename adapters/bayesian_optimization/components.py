"""Small real numerical BO components, independent of the Solver lifecycle."""
from dataclasses import dataclass
import numpy as np


@dataclass(frozen=True)
class FixedRBFConfig:
    length_scale: float = 0.25
    variance: float = 1.0
    observation_variance: float = 0.0
    jitter: float = 1e-8

    def __post_init__(self):
        for name in ("length_scale", "variance", "jitter"):
            value = float(getattr(self, name))
            if not np.isfinite(value) or value <= 0:
                raise ValueError(f"{name} must be finite and positive")
        if not np.isfinite(self.observation_variance) or self.observation_variance < 0:
            raise ValueError("observation_variance must be finite and nonnegative")


class FixedRBFPosterior:
    """Zero-mean exact GP with fixed hyperparameters and latent marginal variance.

    Cholesky caches are rebuilt from the verified portable observation dataset.
    No hyperparameter optimization or undocumented normalization takes place.
    """
    component_state_mode = "rebuild"

    def __init__(self, config=None):
        self.config = config or FixedRBFConfig()
        self.x = self.y = self.cholesky = self.alpha = None

    def describe(self):
        return {"type": "fixed_rbf_gp/v1", **vars(self.config)}

    def spawn(self):
        """Fresh numerical cache with the same fixed interpretation."""
        return type(self)(self.config)

    def kernel(self, left, right):
        delta = np.asarray(left)[:, None, :] - np.asarray(right)[None, :, :]
        return self.config.variance * np.exp(-0.5 * np.sum(delta ** 2, axis=2)
                                              / self.config.length_scale ** 2)

    def fit(self, x, y):
        x = np.array(x, dtype=float, copy=True)
        y = np.array(y, dtype=float, copy=True).reshape(-1)
        if x.ndim != 2 or len(x) != len(y) or not len(x) or not np.isfinite(x).all() or not np.isfinite(y).all():
            raise ValueError("GP requires aligned finite, nonempty X/Y")
        covariance = self.kernel(x, x)
        covariance.flat[::len(x) + 1] += self.config.observation_variance + self.config.jitter
        cholesky = np.linalg.cholesky(covariance)
        alpha = np.linalg.solve(cholesky.T, np.linalg.solve(cholesky, y))
        self.x, self.y, self.cholesky, self.alpha = x, y, cholesky, alpha
        return self

    def posterior(self, x):
        if self.alpha is None:
            raise RuntimeError("GP has not been fitted")
        x = np.asarray(x, dtype=float)
        if x.ndim != 2 or x.shape[1] != self.x.shape[1] or not np.isfinite(x).all():
            raise ValueError("GP query must be a finite aligned matrix")
        cross = self.kernel(x, self.x)
        mean = cross @ self.alpha
        projected = np.linalg.solve(self.cholesky, cross.T)
        variance = np.maximum(0.0, self.config.variance - np.sum(projected ** 2, axis=0))
        return mean, np.sqrt(variance)


@dataclass(frozen=True)
class LowerConfidenceBound:
    component_state_mode = "stateless"
    beta: float = 2.0

    def __post_init__(self):
        if not np.isfinite(self.beta) or self.beta < 0:
            raise ValueError("LCB beta must be finite and nonnegative")

    def describe(self):
        return {"type": "lower_confidence_bound/v1", "beta": self.beta}

    def __call__(self, mean, std):
        return np.asarray(mean) - self.beta * np.asarray(std)


class GridAcquisitionOptimizer:
    """Deterministic argmin; ties retain the declared grid order."""
    component_state_mode = "stateless"
    def __init__(self, grid=((0.25,), (0.5,), (0.75,))):
        self.grid = np.array(grid, dtype=float, copy=True)
        if self.grid.ndim != 2 or not len(self.grid) or not np.isfinite(self.grid).all():
            raise ValueError("acquisition grid must be a finite nonempty matrix")
        self.grid.setflags(write=False)

    def describe(self):
        return {"type": "grid_acquisition/v1", "grid": self.grid.tolist()}

    def minimize(self, model, acquisition):
        mean, std = model.posterior(self.grid)
        values = np.asarray(acquisition(mean, std), dtype=float)
        if values.shape != (len(self.grid),) or not np.isfinite(values).all():
            raise ValueError("acquisition must return one finite value per grid row")
        index = int(np.argmin(values))
        return self.grid[index:index + 1].copy(), {
            "grid": self.grid.tolist(), "mean": mean.tolist(), "std": std.tolist(),
            "acquisition": values.tolist(), "selected_index": index}
