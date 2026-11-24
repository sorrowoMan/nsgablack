"""Split a read-only Pool by occurrences in one local selection invocation."""
from __future__ import annotations

import inspect

import numpy as np

from .change_pool import Pool, _PoolCoordinates, _pure_pool_choice
from .selection_pool import pool_selection_indices


def _choose_call(function, rng):
    if not callable(function):
        raise TypeError("partition by must be a callable choose(Pool[, *, rng])")
    call = getattr(function, "__call__", function)
    if any(check(target) for target in (function, call) for check in (
            inspect.iscoroutinefunction, inspect.isgeneratorfunction,
            inspect.isasyncgenfunction)):
        raise TypeError("partition choose must be an ordinary synchronous function")
    if rng is not None and not isinstance(rng, np.random.Generator):
        raise TypeError("partition rng must be a numpy.random.Generator")
    try:
        signature = inspect.signature(function)
    except (TypeError, ValueError) as exc:
        raise TypeError("partition choose must expose a supported signature") from exc
    probe = object()
    try:
        signature.bind(probe, rng=probe)
        with_rng = True
    except TypeError:
        with_rng = False
    try:
        signature.bind(probe)
        without_rng = True
    except TypeError:
        without_rng = False
    if not with_rng and not without_rng:
        raise TypeError("partition choose must accept choose(Pool[, *, rng])")
    if rng is not None and with_rng:
        return {"rng": rng}, False
    return {}, not without_rng


def partition(pool: Pool, *, by, rng: np.random.Generator | None = None) -> tuple[Pool, Pool]:
    """Return selected occurrences and their complement without changing a pool.

    ``by`` receives a temporary, read-only Pool and must return its derivative.
    It is called once for nonempty input, never for empty input. A supplied RNG
    is forwarded when the callable accepts it; a required RNG must be supplied
    for nonempty input. Callback failures propagate without retries.

    The selected half keeps the rule's order; the remaining half keeps input
    order. Both retain the caller's coordinates and access lifetime. Repeated
    references at different input positions are distinct occurrences, but a
    rule cannot select the same local position twice. No candidates, Units,
    evaluations, membership edits, or persistent position IDs are created.
    """
    if not isinstance(pool, Pool):
        raise TypeError("partition requires an explicit Pool")
    refs = pool.refs  # Also verify that the caller's scope is still open.
    kwargs, needs_rng = _choose_call(by, rng)
    if not refs:
        return pool.take(()), pool.take(())
    if needs_rng:
        raise TypeError("partition choose requires an explicit rng Generator")

    # A new local root distinguishes occurrences even when the input was itself
    # obtained by repeating one of an outer selection's positions. Copy only
    # the lightweight selection view; candidate values remain in the store.
    if pool._root.objectives is None or pool._root.violations is None:
        root = _PoolCoordinates(refs)
    else:
        objectives, violations = pool.selection_feedback()
        root = _PoolCoordinates(refs, objectives, violations)
    if pool._root.member_rows is not None:
        root = _PoolCoordinates(root.refs, root.objectives, root.violations,
            pool._root.member_fields,
            tuple(pool._root.member_rows[i] for i in pool._positions))
    offered = pool._scope._selection(refs, root=root, positions=tuple(range(len(refs))))
    with _pure_pool_choice():
        result = by(offered, **kwargs)
        selected = pool_selection_indices(offered, result)
    chosen = set(selected)
    remaining = tuple(index for index in range(len(refs)) if index not in chosen)
    # Never let the temporary root escape as a new outer survivor identity.
    return pool.take(selected), pool.take(remaining)
