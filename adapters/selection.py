"""Read-only offered-row selection; purpose preserves the algorithm's meaning."""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
import inspect
from types import MappingProxyType

import numpy as np


def _readonly(value, *, dtype=float):
    array = np.asarray(value, dtype=dtype)
    return np.frombuffer(array.tobytes(), dtype=array.dtype).reshape(array.shape)


def _parameters(value, *, active=None):
    if value is None or type(value) in (bool, int, float, str):
        return value
    if isinstance(value, np.generic):
        return _parameters(value.item(), active=active)
    if isinstance(value, np.ndarray):
        if value.dtype.kind not in "biuf":
            raise TypeError("selection parameters require numeric arrays")
        return _readonly(value, dtype=value.dtype)
    if isinstance(value, (Mapping, tuple, list)):
        active = set() if active is None else active
        if id(value) in active:
            raise TypeError("selection parameters cannot contain cycles")
        active.add(id(value))
        try:
            if isinstance(value, Mapping):
                if any(not isinstance(key, str) for key in value):
                    raise TypeError("selection parameter names must be strings")
                return MappingProxyType({key: _parameters(item, active=active) for key, item in value.items()})
            return tuple(_parameters(item, active=active) for item in value)
        finally:
            active.remove(id(value))
    raise TypeError("selection parameters must be detached data, not runtime services")


@dataclass(frozen=True)
class SelectionRequest:
    """One explicit selection decision over immutable offered rows.

    Objectives/violations are the consumer's selection feedback view. Optional
    scores are algorithm-specific comparisons (e.g. a MOEA/D direction), never
    replacements for Problem raw evidence. Indices are local to this request.
    """

    purpose: str
    candidates: object
    objectives: object
    violations: object
    count: int
    scores: object = None
    parameters: object = None
    context: object = None
    pool: object = None

    def __post_init__(self):
        if self.purpose not in {"survivor", "replacement", "candidate", "proposal_order"}:
            raise ValueError("selection purpose must identify a supported decision scope")
        candidates = _readonly(self.candidates)
        objectives = _readonly(self.objectives)
        violations = _readonly(self.violations).reshape(-1)
        n = len(violations)
        if candidates.ndim != 2 or candidates.shape[0] != n:
            raise ValueError("selection candidate rows must align with violations")
        if objectives.ndim == 1:
            objectives = objectives.reshape(-1, 1)
        if objectives.ndim != 2 or objectives.shape[0] != n:
            raise ValueError("selection objectives must align with offered candidates")
        if type(self.count) is not int or not 1 <= self.count <= n:
            raise ValueError("selection count must be within the offered row count")
        scores = None if self.scores is None else _readonly(self.scores).reshape(-1)
        if scores is not None and len(scores) != n:
            raise ValueError("selection scores must align with offered candidates")
        if self.pool is not None:
            from .change_pool import Pool
            if not isinstance(self.pool, Pool) or len(self.pool) != n:
                raise ValueError("selection Pool must align with the offered rows")
            if not np.array_equal(self.pool.values, candidates, equal_nan=True):
                raise ValueError("selection Pool candidates differ from the offered rows")
            pool_obj, pool_vio = self.pool.selection_feedback()
            if (not np.array_equal(pool_obj, objectives, equal_nan=True)
                    or not np.array_equal(pool_vio, violations, equal_nan=True)):
                raise ValueError("selection Pool feedback differs from the offered view")
        if self.context is not None and not isinstance(self.context, Mapping):
            raise TypeError("selection context must be a Mapping")
        context = {key: value for key, value in (self.context or {}).items()
                   if isinstance(key, str) and (value is None or type(value) in (bool, int, float, str))}
        parameters = {} if self.parameters is None else self.parameters
        if not isinstance(parameters, Mapping):
            raise TypeError("selection parameters must be a Mapping")
        for name, value in (("candidates", candidates), ("objectives", objectives),
                            ("violations", violations), ("scores", scores)):
            object.__setattr__(self, name, value)
        object.__setattr__(self, "parameters", _parameters(parameters))
        object.__setattr__(self, "context", MappingProxyType(context))


class OrdinaryPoolSelection:
    """Bridge a Pool choice, optionally with named branches, into a selector."""

    stateless = True

    def __init__(self, function):
        from .change import _function_identity
        from functools import partial
        _function_identity(function)
        signature = inspect.signature(function)
        count_parameter = signature.parameters.get("count")
        self._with_count = (count_parameter is not None
                            and count_parameter.kind in (inspect.Parameter.POSITIONAL_OR_KEYWORD,
                                                         inspect.Parameter.KEYWORD_ONLY)
                            and not (isinstance(function, partial)
                                     and "count" in (function.keywords or {})))
        kwargs = {"count": object()} if self._with_count else {}
        try:
            signature.bind(object(), rng=object(), **kwargs)
            self._with_rng = True
        except TypeError:
            signature.bind(object(), **kwargs)
            self._with_rng = False
        self.function = function

    def checkpoint_identity(self):
        from .change import _function_identity
        identity = {"schema": "nsgablack.pool_selection/v1", "function": _function_identity(self.function),
                    "with_rng": self._with_rng}
        if self._with_count:
            identity.update(schema="nsgablack.pool_selection/v2", with_count=True)
        return identity

    def select(self, request, *, rng):
        if not isinstance(request, SelectionRequest) or request.pool is None:
            raise ValueError("ordinary choose requires exact offered Pool versions; array-only input is unsupported")
        kwargs = {"count": request.count} if self._with_count else {}
        if self._with_rng:
            kwargs["rng"] = rng
        result = self.function(request.pool, **kwargs)
        from .change_pool import Pool
        if (isinstance(result, tuple) and len(result) == 2
                and isinstance(result[0], Pool) and isinstance(result[1], Mapping)):
            if request.purpose != "survivor":
                raise ValueError("named selection outputs require a survivor selection purpose")
            return result
        if not isinstance(result, Pool):
            raise TypeError("ordinary choose must return a Pool or (Pool, name-to-Pool Mapping)")
        return result


@dataclass(frozen=True)
class FeasibilityFirstSelection:
    """Rank by feasibility, violation, then supplied score (or one objective).

    This explicitly chosen policy is not Pareto environmental selection or a
    replacement for Metropolis. Its result still passes the owner's guards.
    """

    objective_index: int = 0
    constraint_tolerance: float = 0.0
    stateless = True

    def __post_init__(self):
        if type(self.objective_index) is not int or self.objective_index < 0:
            raise ValueError("objective_index must be a nonnegative integer")
        if (isinstance(self.constraint_tolerance, bool)
                or not isinstance(self.constraint_tolerance, (int, float))
                or not np.isfinite(self.constraint_tolerance)):
            raise ValueError("constraint_tolerance must be finite")

    def checkpoint_identity(self):
        return {"objective_index": self.objective_index, "constraint_tolerance": self.constraint_tolerance}

    def select(self, request, *, rng):
        del rng
        if not isinstance(request, SelectionRequest):
            raise TypeError("selector requires SelectionRequest")
        if request.scores is None:
            if not 0 <= self.objective_index < request.objectives.shape[1]:
                raise ValueError("selector objective_index is outside the feedback dimensions")
            scores = request.objectives[:, self.objective_index]
        else:
            scores = request.scores
        violations = request.violations
        feasible = np.isfinite(violations) & (violations <= self.constraint_tolerance)
        order = sorted(range(len(violations)), key=lambda i: (
            not bool(feasible[i]), 0.0 if feasible[i] else float(violations[i]) if np.isfinite(violations[i]) else np.inf,
            float(scores[i]) if np.isfinite(scores[i]) else np.inf, i))
        return tuple(order[:request.count])
