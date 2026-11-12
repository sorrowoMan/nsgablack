"""Replaceable MAP-Elites descriptor, grid, competition and proposal components."""
from dataclasses import dataclass
import numpy as np


@dataclass(frozen=True)
class IdentityDescriptor:
    """Behavior coordinates equal selected coordinates of the evaluated point."""
    indices: tuple[int, ...] | None = None
    stateless = True

    def checkpoint_identity(self):
        return {"kind": "identity_descriptor/v1", "indices": self.indices}

    def describe(self, candidate, feedback):
        from ...units.contracts import candidate_array
        x = candidate_array(candidate).reshape(-1)
        return np.array(x if self.indices is None else x[list(self.indices)], copy=True)


@dataclass(frozen=True)
class GridCells:
    """Half-open cells; the declared upper domain boundary belongs to the last cell."""
    lower: tuple[float, ...] = (0., 0.)
    upper: tuple[float, ...] = (1., 1.)
    bins: tuple[int, ...] = (2, 2)
    stateless = True

    def __post_init__(self):
        object.__setattr__(self, "lower", tuple(float(x) for x in self.lower))
        object.__setattr__(self, "upper", tuple(float(x) for x in self.upper))
        object.__setattr__(self, "bins", tuple(self.bins))
        if (not self.bins or len(self.lower) != len(self.bins) or len(self.upper) != len(self.bins)
                or any(type(n) is not int or n < 1 for n in self.bins)
                or not np.all(np.isfinite([self.lower, self.upper]))
                or np.any(np.asarray(self.upper) <= self.lower)):
            raise ValueError("grid requires aligned finite bounds and positive integer bins")

    def checkpoint_identity(self):
        return {"kind": "grid_cells/v1", "lower": self.lower, "upper": self.upper, "bins": self.bins}

    def locate(self, descriptor):
        value = np.asarray(descriptor, dtype=float).reshape(-1)
        lo, hi, bins = np.asarray(self.lower), np.asarray(self.upper), np.asarray(self.bins)
        if value.shape != lo.shape or not np.all(np.isfinite(value)) or np.any(value < lo) or np.any(value > hi):
            raise ValueError("behavior descriptor is outside its declared grid")
        return tuple(int(i) for i in np.minimum(np.floor((value-lo)/(hi-lo)*bins).astype(int), bins-1))


@dataclass(frozen=True)
class MinimizeObjective:
    """Feasibility first, then one raw objective; exact ties retain the old champion."""
    objective: int = 0
    tolerance: float = 0.
    stateless = True

    def __post_init__(self):
        if type(self.objective) is not int or self.objective < 0 or not np.isfinite(self.tolerance) or self.tolerance < 0:
            raise ValueError("invalid archive quality configuration")

    def checkpoint_identity(self):
        return {"kind": "minimize_raw_objective/v1", "objective": self.objective, "tolerance": self.tolerance}

    def quality(self, objectives):
        return float(objectives[self.objective])

    def prefer(self, challenger, incumbent):
        if incumbent is None:
            return True
        v, old_v = max(0., challenger["violation"]), max(0., incumbent["violation"])
        if (v > 0) != (old_v > 0):
            return v <= 0
        if v != old_v:
            return v < old_v
        return challenger["quality"] < incumbent["quality"] - self.tolerance


class SequenceEmitter:
    """Finite explicit proposals for reproducible examples and fault injection."""
    stateless = False

    def __init__(self, points):
        array = np.asarray(points, dtype=float)
        if array.ndim != 2 or not len(array) or not np.all(np.isfinite(array)):
            raise ValueError("sequence points must be a finite nonempty matrix")
        self.points = tuple(tuple(float(x) for x in row) for row in array)
        self.cursor = 0

    def checkpoint_identity(self):
        return {"kind": "sequence_emitter/v1", "points": self.points}

    def get_state(self):
        return {"cursor": self.cursor}

    def set_state(self, state):
        cursor = state.get("cursor")
        if set(state) != {"cursor"} or type(cursor) is not int or not 0 <= cursor <= len(self.points):
            raise ValueError("invalid sequence emitter cursor")
        self.cursor = cursor

    @property
    def exhausted(self):
        return self.cursor == len(self.points)

    def emit(self, archive, count, *, rng, control, context):
        rows = self.points[self.cursor:self.cursor+count]
        self.cursor += len(rows)
        return tuple(np.asarray(row, dtype=float) for row in rows)


@dataclass(frozen=True)
class GaussianArchiveEmitter:
    """Mutate a champion position; obtain initialization from the ordinary Pipeline."""
    sigma: float = 0.1
    stateless = True

    def __post_init__(self):
        if not np.isfinite(self.sigma) or self.sigma < 0:
            raise ValueError("emitter sigma must be finite and nonnegative")

    def checkpoint_identity(self):
        return {"kind": "gaussian_archive_emitter/v1", "sigma": self.sigma}

    def emit(self, archive, count, *, rng, control, context):
        from ..pool_results import PoolRefinementState
        from ...core.state.solution_pool import SolutionRef
        if not archive:
            rows = []
            for candidate in control.init_population(count, context):
                seed = PoolRefinementState()
                seed.remember_seed(control, candidate)
                rows.append(seed.project_current(control, np.asarray(candidate), semantic=True))
            return tuple(rows)
        rows = []
        for _ in range(count):
            entry = archive[int(rng.integers(len(archive)))]
            ref = SolutionRef.from_dict(dict(entry["solution_ref"]))
            seed = control.read_solutions((ref,)).semantic_states[0]
            source = PoolRefinementState()
            source.remember_seed(control, seed)
            value = np.asarray(seed.values) + rng.normal(0., self.sigma, size=np.asarray(seed.values).shape)
            rows.append(source.derive_candidate(control, value, stage="map_elites_emitter"))
        return tuple(rows)
