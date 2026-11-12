"""Explicit zero-to-many results for one ordinary candidate-change call."""
from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, replace

import numpy as np

from .change_pool import ChangeResult


@dataclass(frozen=True, init=False)
class ChangeBatchResult:
    """An ordered result sequence, with separate sources and outputs per child.

    An empty sequence explicitly means no proposals. A numeric matrix is never
    guessed to be a batch: wrap every child in ``ChangeResult``.
    """

    results: tuple[ChangeResult, ...]

    def __init__(self, results=()):
        if not isinstance(results, Sequence) or isinstance(results, (str, bytes)):
            raise TypeError("change batch results require an ordered sequence of ChangeResult")
        items = tuple(results)
        if any(not isinstance(item, ChangeResult) for item in items):
            raise TypeError("change batch results require an ordered sequence of ChangeResult")
        object.__setattr__(self, "results", items)

    def __len__(self):
        return len(self.results)

    def __iter__(self):
        return iter(self.results)


class _ConstantChange:
    """Return an already computed child through the control-plane mutation seam."""

    def __init__(self, candidate):
        self.candidate = candidate

    def mutate(self, candidate, context):
        return self.candidate


def apply_function_change_batch(owner, control, candidate, request, context, *, rng, max_outputs):
    """Calculate once, then bind each child as a distinct proposal in order.

    The existing control plane owns candidate identity, normalization, repair,
    evaluation and eventual output publication. This bridge performs no repair
    or evaluation and does not publish any Pool memberships.
    """
    from .change import (ChangeRequest, _bind_change_result, _change_scope,
                         _prepare_change_result)

    operation = owner.get_bound_change()
    if operation is None:
        raise ValueError("no complete change function is bound")
    if not isinstance(request, ChangeRequest):
        raise TypeError("complete change requires ChangeRequest")
    if (not isinstance(max_outputs, (int, np.integer))
            or isinstance(max_outputs, (bool, np.bool_)) or max_outputs < 0):
        raise ValueError("batch change max_outputs must be a nonnegative integer")
    limit = int(max_outputs)
    pool, scope = _change_scope(control, request, context)
    scoped_request = replace(request, pool=scope, max_outputs=limit)
    try:
        value = operation.change(scoped_request, rng=rng)
        # Single-candidate functions remain useful on a batch-capable consumer.
        results = value.results if isinstance(value, ChangeBatchResult) else (value,)
        if len(results) > limit:
            raise ValueError("change batch exceeds the declared max_outputs allowance")
        # Preflight every item before creating the first child. In particular,
        # malformed later results must not make earlier results look complete.
        prepared = tuple(_prepare_change_result(result, scoped_request, pool) for result in results)
        children = []
        for result, outputs, edits in prepared:
            child = control.mutate_candidate(candidate, context,
                mutator=_ConstantChange(result.candidate))
            children.append(_bind_change_result(control, child, request, scope,
                                               result, outputs, edits))
        return tuple(children)
    finally:
        if scope is not None:
            scope.close()
