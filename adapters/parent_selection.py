"""Independent parent selection over exact, published solution references.

Selectors receive a detached population ranking, a pool and an explicit RNG.
They never need an Adapter's private population or control-plane services.
"""
from __future__ import annotations

from dataclasses import dataclass
from contextlib import contextmanager
from types import MappingProxyType
from typing import Any, Mapping

import numpy as np

from ..core.state.solution_pool import SolutionRef


def _readonly(values, *, dtype):
    array = np.asarray(values, dtype=dtype).reshape(-1)
    # An immutable bytes owner prevents callers from re-enabling write access.
    return np.frombuffer(array.tobytes(), dtype=array.dtype)


@dataclass(frozen=True)
class ParentSelectionRequest:
    """Detached inputs; context carries scalar call-local values only.

    The caller deliberately excludes services, arrays and shared mutable
    context values. Unit dependencies are the explicit ranking fields here.
    """

    population_refs: tuple[SolutionRef, ...]
    rank: np.ndarray
    crowding: np.ndarray
    count: int
    context: Mapping[str, Any]
    members: object = None

    def __post_init__(self):
        refs = tuple(self.population_refs)
        if not refs or any(not isinstance(ref, SolutionRef) for ref in refs):
            raise ValueError("parent selection requires exact population SolutionRefs")
        if type(self.count) is not int or self.count < 1:
            raise ValueError("parent selection count must be a positive integer")
        rank = _readonly(self.rank, dtype=int)
        crowding = _readonly(self.crowding, dtype=float)
        if len(rank) != len(refs) or len(crowding) != len(refs):
            raise ValueError("parent selection rankings must align with population references")
        if not isinstance(self.context, Mapping) or any(
            not isinstance(key, str) or not (value is None or type(value) in (str, bool, int, float))
            for key, value in self.context.items()
        ):
            raise TypeError("parent selection context must contain only named scalar values")
        object.__setattr__(self, "population_refs", refs)
        object.__setattr__(self, "rank", rank)
        object.__setattr__(self, "crowding", crowding)
        object.__setattr__(self, "context", MappingProxyType(dict(self.context)))
        if self.members is not None:
            from .change_pool import Pool
            if not isinstance(self.members, Pool) or self.members.refs != refs:
                raise ValueError("parent selection members must retain exact population slot order")


def resolve_parent_selection(request, result):
    """Keep explicit Pool occurrences; legacy references require unique slots."""
    from .change_pool import Pool
    from .selection_pool import pool_selection_indices
    if isinstance(result, Pool):
        if request.members is None:
            raise ValueError("Pool parent selection requires supplied request.members")
        indices = pool_selection_indices(request.members, result, allow_repeated=True)
        refs = result.refs
    else:
        if isinstance(result, (set, frozenset, Mapping, str, bytes)):
            raise ValueError("parent selector must return an ordered sequence of exact SolutionRefs or a member Pool")
        try:
            refs = tuple(result)
        except TypeError as exc:
            raise ValueError("parent selector must return ordered exact SolutionRefs or a member Pool") from exc
        if any(not isinstance(ref, SolutionRef) for ref in refs):
            raise ValueError("parent selector must return exact SolutionRefs, not numeric row guesses")
        slots = {}
        for index, ref in enumerate(request.population_refs):
            slots.setdefault(ref, []).append(index)
        if any(len(slots.get(ref, ())) > 1 for ref in refs):
            raise ValueError("parent reference has multiple member slots; return request.members.take(...) "
                             "to identify the selected occurrences")
        indices = tuple(slots[ref][0] if ref in slots else None for ref in refs)
    if len(refs) != request.count:
        raise ValueError("parent selector must return the requested number of exact SolutionRefs")
    return refs, indices


@contextmanager
def parent_member_pool(owner, control):
    """Read this owner's exact member occurrences without creating a Unit."""
    from .selection_pool import offered_pool
    refs = tuple(owner.get_population_solution_refs(control))
    _, objectives, violations = owner.get_population_snapshot()
    with offered_pool(control, refs, objectives=objectives, violations=violations,
                      unit=owner.algorithm_unit, member_rows=tuple(range(len(refs)))) as members:
        yield members


@contextmanager
def selected_parent_pool(control, members, refs, indices):
    """Expose detached member fields for the chosen parents, including donors.

    External donors have no owner slot. Reading their member field requires an
    explicit default. There is no implicit common selection score for donors.
    """
    from .change_pool import ChangePool, _PoolCoordinates
    scope = ChangePool(control.solution_pool, allowed_refs=refs, allow_main=False)
    try:
        root = _PoolCoordinates(tuple(refs), member_fields=members._root.member_fields,
                                member_rows=tuple(indices))
        yield scope._selection(refs, root=root, positions=tuple(range(len(refs))))
    finally:
        scope.close()


@dataclass(frozen=True)
class MixedPoolParentSelector:
    """Mix ranked population tournaments with uniform named-pool sampling.

    Parent sampling allows replacement, as ordinary genetic tournaments do.
    The requested pool quota is rounded to the nearest integer, then source
    positions are shuffled. The named pool must already exist and be readable.
    """

    pool_name: str
    pool_fraction: float = 0.5
    stateless = True

    def __post_init__(self):
        if not isinstance(self.pool_name, str) or not self.pool_name.strip():
            raise ValueError("parent pool_name must be nonempty")
        if (isinstance(self.pool_fraction, bool) or not isinstance(self.pool_fraction, (int, float))
                or not np.isfinite(self.pool_fraction)
                or not 0.0 <= float(self.pool_fraction) <= 1.0):
            raise ValueError("parent pool_fraction must be finite and between zero and one")

    def checkpoint_identity(self):
        return {"pool_name": self.pool_name, "pool_fraction": float(self.pool_fraction)}

    def select(self, request: ParentSelectionRequest, *, pool, rng):
        if not isinstance(request, ParentSelectionRequest):
            raise TypeError("parent selector requires ParentSelectionRequest")
        if not pool.has_subpool(self.pool_name):
            raise ValueError(f"parent selection pool does not exist: {self.pool_name}")
        external = tuple(pool.subpool_refs(self.pool_name))
        if not external:
            raise ValueError(f"parent selection pool is empty or unpublished: {self.pool_name}")
        if any(not isinstance(ref, SolutionRef) for ref in external):
            raise TypeError("parent pool must contain exact SolutionRefs")
        # Validate scope, versions, tokens and publication before consuming RNG.
        pool.read(request.population_refs)
        pool.read(external)
        external_count = int(np.floor(request.count * float(self.pool_fraction) + 0.5))
        sources = np.zeros(request.count, dtype=bool)
        sources[:external_count] = True
        rng.shuffle(sources)
        selected = []
        for from_pool in sources:
            if from_pool:
                selected.append(external[int(rng.integers(0, len(external)))])
                continue
            left, right = (int(value) for value in rng.integers(0, len(request.population_refs), size=2))
            if request.rank[left] != request.rank[right]:
                winner = left if request.rank[left] < request.rank[right] else right
            else:
                winner = left if request.crowding[left] >= request.crowding[right] else right
            selected.append(request.population_refs[winner])
        return tuple(selected)
