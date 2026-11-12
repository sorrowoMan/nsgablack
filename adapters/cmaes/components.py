"""Small replaceable CMA sampling, ranking and distribution-update components.

No component evaluates the Problem, publishes candidates or owns a run loop.
The positive-weight update follows the standard rank-one + rank-mu CMA rule.
"""
from copy import deepcopy
from dataclasses import asdict, dataclass
import math

import numpy as np


class GaussianCohortSampler:
    """Sample standard normals; an explicit fixed prefix supports formula fixtures."""
    def __init__(self, seed=42, *, fixed_batches=()):
        self.seed = int(seed)
        self.fixed_batches = tuple(np.array(v, dtype=float, copy=True) for v in fixed_batches)
        self.reset()

    @property
    def checkpoint_identity(self):
        return {"schema": "cma.gaussian_sampler/v1", "seed": self.seed,
                "fixed_batches": [v.tolist() for v in self.fixed_batches]}

    def reset(self):
        self._rng = np.random.default_rng(self.seed)
        self._cursor = 0

    def sample(self, count, dimension):
        if self._cursor < len(self.fixed_batches):
            result = self.fixed_batches[self._cursor].copy()
            if result.shape != (count, dimension):
                raise ValueError("CMA fixed cohort shape differs from configured lambda/dimension")
        else:
            result = self._rng.standard_normal((count, dimension))
        self._cursor += 1
        return result

    def get_state(self):
        return {"identity": self.checkpoint_identity, "cursor": self._cursor,
                "rng": deepcopy(self._rng.bit_generator.state)}

    def set_state(self, state):
        if state["identity"] != self.checkpoint_identity or type(state["cursor"]) is not int or state["cursor"] < 0:
            raise ValueError("Incompatible CMA sampler checkpoint")
        rng = np.random.default_rng(self.seed)
        rng.bit_generator.state = deepcopy(state["rng"])
        self._rng, self._cursor = rng, state["cursor"]


class StableObjectiveRanking:
    """Rank raw, unconstrained scalar observations; ties keep proposal order."""
    checkpoint_identity = {"schema": "cma.raw_unconstrained_ranking/v1"}
    stateless = True

    def rank(self, feedback):
        f = np.asarray(feedback.raw_objectives, dtype=float)
        v = np.asarray(feedback.raw_violations, dtype=float)
        if f.ndim != 2 or f.shape[1] != 1 or not np.all(np.isfinite(f)):
            raise ValueError("CMA ranking requires finite scalar raw objectives")
        if not np.all(np.isfinite(v)) or np.any(v > 0):
            raise ValueError("This CMA ranking declares unconstrained observations only")
        return np.argsort(f[:, 0], kind="stable")


@dataclass(frozen=True)
class CMAParameters:
    population_size: int = 4
    parents: int = 2
    weights: tuple | None = None
    cc: float | None = None
    cs: float | None = None
    c1: float | None = None
    cmu: float | None = None
    damping: float | None = None

    def resolve(self, dimension):
        lam, mu, n = self.population_size, self.parents, dimension
        if type(lam) is not int or type(mu) is not int or not 1 <= mu <= lam or lam < 2:
            raise ValueError("CMA requires lambda >= 2 and 1 <= mu <= lambda")
        w = (np.log(mu + .5) - np.log(np.arange(1, mu + 1)) if self.weights is None
             else np.asarray(self.weights, dtype=float))
        if w.shape != (mu,) or not np.all(np.isfinite(w)) or np.any(w <= 0):
            raise ValueError("CMA weights must be finite, positive and align with mu")
        w = w / np.sum(w)
        eff = float(1 / np.sum(w * w))
        cc = (4 + eff / n) / (n + 4 + 2 * eff / n) if self.cc is None else float(self.cc)
        cs = (eff + 2) / (n + eff + 5) if self.cs is None else float(self.cs)
        c1 = 2 / ((n + 1.3) ** 2 + eff) if self.c1 is None else float(self.c1)
        cmu = min(1 - c1, 2 * (eff - 2 + 1 / eff) / ((n + 2) ** 2 + eff)) if self.cmu is None else float(self.cmu)
        damping = 1 + 2 * max(0., math.sqrt((eff - 1) / (n + 1)) - 1) + cs if self.damping is None else float(self.damping)
        if (not all(np.isfinite(v) for v in (cc, cs, c1, cmu, damping))
                or not 0 < cc <= 1 or not 0 < cs < 1 or c1 < 0 or cmu < 0
                or c1 + cmu > 1 or damping <= 0):
            raise ValueError("Invalid positive-weight CMA adaptation parameters")
        # Exact expected norm, including n=1; avoids an asymptotic 1D mismatch.
        chi = math.sqrt(2) * math.exp(math.lgamma((n + 1) / 2) - math.lgamma(n / 2))
        return dict(weights=w, effective_parents=eff, cc=cc, cs=cs, c1=c1, cmu=cmu,
                    damping=damping, chi=chi)


class PositiveCMAUpdate:
    stateless = True
    def __init__(self, parameters=None):
        self.parameters = parameters or CMAParameters()

    @property
    def checkpoint_identity(self):
        return {"schema": "cma.positive_full_covariance_update/v1", "parameters": asdict(self.parameters)}

    def update(self, *, mean, covariance, sigma, path_c, path_sigma, iteration, offsets, ranking):
        n = len(mean)
        p = self.parameters.resolve(n)
        w, eff = p["weights"], p["effective_parents"]
        selected = np.asarray(offsets)[np.asarray(ranking)[:len(w)]]
        yw = np.sum(w[:, None] * selected, axis=0)
        eigenvalues, basis = np.linalg.eigh(covariance)
        invsqrt = (basis * (1 / np.sqrt(eigenvalues))) @ basis.T
        ps = (1 - p["cs"]) * path_sigma + math.sqrt(p["cs"] * (2 - p["cs"]) * eff) * (invsqrt @ yw)
        h = float(np.linalg.norm(ps) / math.sqrt(1 - (1 - p["cs"]) ** (2 * (iteration + 1))) / p["chi"]
                  < 1.4 + 2 / (n + 1))
        pc = (1 - p["cc"]) * path_c + h * math.sqrt(p["cc"] * (2 - p["cc"]) * eff) * yw
        rank_mu = np.einsum("i,ij,ik->jk", w, selected, selected)
        new_cov = ((1 - p["c1"] - p["cmu"]) * covariance
            + p["c1"] * (np.outer(pc, pc) + (1 - h) * p["cc"] * (2 - p["cc"]) * covariance)
            + p["cmu"] * rank_mu)
        new_cov = (new_cov + new_cov.T) / 2
        return dict(mean=np.asarray(mean) + sigma * yw, covariance=new_cov,
            sigma=float(sigma * math.exp(p["cs"] / p["damping"] * (np.linalg.norm(ps) / p["chi"] - 1))),
            path_c=pc, path_sigma=ps, iteration=iteration + 1, h_sigma=int(h))
