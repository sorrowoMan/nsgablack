"""Exact offered rows for one owner-controlled selection invocation."""
from __future__ import annotations

from collections.abc import Mapping
from contextlib import contextmanager

import numpy as np

from .change_pool import ChangePool, Pool, _PoolCoordinates, _readonly, _refs
from ..core.state.solution_pool import SolutionPool


def member_coordinates(unit, member_rows, count):
    """Freeze one owner's declared fields with explicit occurrence coordinates."""
    fields = None
    if unit is not None:
        from types import MappingProxyType
        if member_rows is None:
            raise ValueError("Unit-backed selection requires explicit member row coordinates")
        member_rows = tuple(member_rows)
        size = 0 if unit.population is None else len(unit.population)
        if len(member_rows) != count or any(
                row is not None and (type(row) is not int or not 0 <= row < size)
                for row in member_rows):
            raise ValueError("member rows must align with offered positions and Unit slots")
        fields = {}
        for name in unit.member_fields:
            values = getattr(unit, name)
            if not isinstance(values, (np.ndarray, list, tuple)) or (isinstance(values, np.ndarray) and values.ndim == 0) or len(values) != size:
                raise ValueError("selection member fields must align with Unit slots")
            if isinstance(values, np.ndarray) and values.dtype.kind in "biuf":
                fields[name] = _readonly(values)
            else:
                from ..units.features import _detached_readonly
                fields[name] = _detached_readonly(values)
        fields = MappingProxyType(fields)
    elif member_rows is not None:
        raise ValueError("member rows require a Unit owner")
    return fields, member_rows


@contextmanager
def offered_pool(control, solution_refs, *, objectives, violations, accepted_refs=(),
                 unit=None, member_rows=None):
    """Grant only supplied published/accepted versions, until the owner returns.

    Feedback is the already computed selection view. Raw evaluation remains in
    the existing pool records and is read only through ``raw_feedback``.
    """
    store = getattr(control, "solution_pool", None)
    if not isinstance(store, SolutionPool):
        raise TypeError("offered pool requires the control plane's SolutionPool")
    refs, accepted = _refs(solution_refs), _refs(accepted_refs)
    if not set(accepted).issubset(refs):
        raise ValueError("accepted selection capability exceeds the offered versions")
    obj, vio = _readonly(objectives), _readonly(violations)
    if obj.ndim == 1:
        obj = obj.reshape(-1, 1)
    if obj.ndim != 2 or len(obj) != len(refs) or vio.ndim != 1 or len(vio) != len(refs):
        raise ValueError("offered pool feedback must align with exact references")
    fields, member_rows = member_coordinates(unit, member_rows, len(refs))
    scope = ChangePool(store, allowed_refs=refs, allow_main=False, accepted_refs=accepted)
    try:
        root = _PoolCoordinates(refs, obj, vio, fields, member_rows)
        yield scope._selection(refs, root=root, positions=tuple(range(len(refs))))
    finally:
        scope.close()


def pool_selection_indices(offered, result, *, allow_repeated=False):
    """Recover positions without matching equal values or repeated references."""
    if not isinstance(offered, Pool) or not isinstance(result, Pool):
        raise TypeError("Pool selection requires an explicit offered Pool")
    offered._scope._open()
    result._scope._open()
    if result._scope is not offered._scope or result._root is not offered._root:
        raise ValueError("selected Pool must retain this request's offered root and scope")
    positions = tuple(result._positions)
    allowed = set(offered._positions)
    if (any(type(position) is not int or position not in allowed for position in positions)
            or tuple(result._root.refs[position] for position in positions) != result.refs):
        raise ValueError("selected Pool exceeds the offered positions")
    if not allow_repeated and len(set(positions)) != len(positions):
        raise ValueError("survivor selection cannot repeat an offered position")
    # The request can itself be a reordered view. Its indices remain local.
    local = {position: index for index, position in enumerate(offered._positions)}
    if len(local) != len(offered._positions):
        raise ValueError("offered selection positions must be distinct")
    return tuple(local[position] for position in positions)


def stage_selection_outputs(offered, outputs):
    """Detach named branch selections into ordinary member plans, without I/O."""
    from .change_pool import PoolEdit
    from .change_outputs import _target
    from .pool_maintenance import collect_selection_edits

    if not isinstance(offered, Pool) or not isinstance(outputs, Mapping):
        raise TypeError("named selection outputs require an offered Pool and a name-to-Pool Mapping")
    offered._scope._open()
    pool = offered._scope._pool
    plans = []
    for name, selected in outputs.items():
        if not isinstance(name, str) or not name.strip():
            raise ValueError("named selection output name must be nonempty")
        # Branch collections retain explicit order and repetitions, but never
        # acquire new inputs or launder the main survivor's coordinates.
        try:
            pool_selection_indices(offered, selected, allow_repeated=True)
            target = _target(pool, name, True)
        except (TypeError, ValueError, KeyError) as exc:
            raise type(exc)(f"selection output {name!r}: {exc}") from exc
        expected = (target["descriptor"] if target["descriptor"] is not None
                    else {"pool_id": pool.pool_id, "name": name, "absent": True})
        plans.append(PoolEdit(name, selected.refs, expected=expected))
    if plans:
        collect_selection_edits(pool, plans)
