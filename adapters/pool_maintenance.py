"""Batch member decisions inside the owning Adapter's existing update.

Only detached read capabilities and replacement plans cross this boundary.
The call-local collector joins normal change outputs at the existing publish
point; it owns neither a lifecycle nor a second transaction.
"""
from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
import inspect
from types import MappingProxyType

import numpy as np

from .change import _function_identity
from .change_access import current_change_access
from .change_pool import ChangePool, Pool, PoolEdit, _PoolCoordinates, _readonly, _refs
from ..core.state.solution_pool import SolutionRef
from ..units.features import _detached_readonly


@dataclass(frozen=True)
class PoolMaintenanceRequest:
    pool: ChangePool
    accepted: Pool
    objectives: object
    violations: object
    parameters: object
    context: object
    # The actual leaf's ordered final population, not all admitted trials.
    # Trajectory owners deliberately have no population result here.
    members: Pool | None = None
    # Composite maintenance keeps each owner's feedback/fields separate.
    # members is then a raw-only concatenation of these ordered references.
    members_by_owner: object = None


class OrdinaryPoolMaintenance:
    """Wrap a synchronous ordinary function in the existing binding codec."""

    stateless = True

    def __init__(self, function):
        inspect.signature(function).bind(object(), rng=object())
        _function_identity(function)
        self.function = function

    def checkpoint_identity(self):
        return {"schema": "nsgablack.pool_maintenance/v1",
                "function": _function_identity(self.function)}

    def maintain(self, request, *, rng):
        return self.function(request, rng=rng)


_member_plans = ContextVar("nsgablack_pool_member_plans", default=None)


class _PoolMemberPlans(list):
    """Existing update collector, also carrying append-only working-area claims."""

    def __init__(self):
        super().__init__()
        self.working_outputs = {}
        self.working_claimed = set()


@contextmanager
def collecting_pool_edits(pool):
    """Collect this update's plans without persisting pending callback state."""
    edits = _PoolMemberPlans()
    token = _member_plans.set((pool, edits))
    try:
        yield edits
    finally:
        _member_plans.reset(token)


def collect_selection_edits(pool, edits):
    """Join exact selection outputs to this update's existing plan collector."""
    sink = require_pool_edit_collector(pool)
    sink.extend(edits)


def require_pool_edit_collector(pool):
    """Require the existing update transaction before staging any local write."""
    sink = _member_plans.get()
    if sink is None or sink[0] is not pool or not pool._in_attempt:
        raise RuntimeError("named selection outputs require the owning Solver update transaction")
    return sink[1]


def collect_working_pool_results(pool, descriptor, refs):
    """Join nearest-area append claims to this same update's publication plan."""
    sink = require_pool_edit_collector(pool)
    refs = tuple(ref for ref in refs if ref not in sink.working_claimed)
    if not refs:
        return
    name = descriptor["name"]
    from .change_outputs import _target
    target = _target(pool, name, False)
    if target["descriptor"] != descriptor:
        raise ValueError("working_pool identity or revision changed during the update")
    if name in sink.working_outputs:
        previous, members = sink.working_outputs[name]
        if previous != target:
            raise ValueError("conflicting working_pool bindings in one update")
        members.extend(refs)
    else:
        sink.working_outputs[name] = (target, list(refs))
    sink.working_claimed.update(refs)


def _feedback_pool(scope, refs, objectives, violations, *, unit=None):
    """Attach this owner's already computed view without projecting raw data."""
    refs = _refs(refs)
    obj, vio = _readonly(objectives), _readonly(violations)
    if obj.ndim == 1:
        obj = obj.reshape(-1, 1)
    if obj.ndim != 2 or len(obj) != len(refs) or vio.ndim != 1 or len(vio) != len(refs):
        raise ValueError("pool maintenance feedback must align with exact references")
    from .selection_pool import member_coordinates
    fields, rows = member_coordinates(unit, tuple(range(len(refs))) if unit is not None else None,
                                      len(refs))
    return scope._selection(refs, root=_PoolCoordinates(refs, obj, vio, fields, rows),
                            positions=tuple(range(len(refs))))


def _final_members(owner, control, accepted_refs):
    """Read the leaf's existing population contract, never retention roots.

    Only this leaf's admitted rows may be uncommitted. Other members must be
    published versions even if another branch has pending records in the pool.
    """
    refs = owner.get_population_solution_refs(control)
    snapshot = owner.get_population_snapshot()
    if refs is None and snapshot is None:
        return None
    if refs is None or snapshot is None:
        raise ValueError(f"{owner.name}: pool maintenance requires aligned population refs and snapshot")
    refs = _refs(refs)
    if not isinstance(snapshot, (tuple, list)) or len(snapshot) != 3:
        raise ValueError(f"{owner.name}: pool maintenance requires a population (X, F, V) snapshot")
    pop, obj, vio = (np.asarray(value, dtype=float) for value in snapshot)
    if (pop.ndim != 2 or obj.ndim != 2 or vio.ndim != 1
            or len(pop) != len(refs) or len(obj) != len(refs) or len(vio) != len(refs)):
        raise ValueError(f"{owner.name}: pool maintenance population rows must align with exact references")
    pool = control.solution_pool
    accepted = frozenset(accepted_refs)
    for ref in refs:
        if ref in accepted:
            record = pool._record(ref, allow_pending=True)
            if record.stage != "accepted" or not pool._in_attempt:
                raise ValueError(f"{owner.name}: pool maintenance requires this leaf's admitted members")
        else:
            pool.stamp_for(ref)  # Reject sibling pending data, not merely bad IDs.
    if refs and not np.array_equal(pool.read(refs, allow_pending=True).numeric_matrix, pop, equal_nan=True):
        raise ValueError(f"{owner.name}: pool maintenance population differs from its exact member versions")
    return refs, obj, vio


def population_member_owners(root, children):
    """Resolve descendants through the existing ownership tree, without Units."""
    children = tuple(children)
    selected = {id(child) for child in children}
    if len(selected) != len(children):
        raise ValueError("composite maintenance requires unique active children")
    result, seen = [], set()
    def visit(child, path, active=False):
        if id(child) in seen:
            raise ValueError("composite maintenance requires unique child ownership")
        seen.add(id(child))
        active = active or id(child) in selected
        descendants = tuple(child.step_transaction_children())
        if descendants:
            for index, descendant in enumerate(descendants):
                visit(descendant, (*path, f"{index}:{descendant.name}"), active)
        elif active:
            result.append(("/".join(path), child))
    # Same canonical path as adapter_path, but only one ownership walk for all
    # active branches, rather than rewalking the full tree for every leaf.
    visit(root, (root.name,))
    if not selected.issubset(seen):
        raise ValueError("composite maintenance child is outside the owner's Adapter tree")
    return tuple(result)


def run_pool_maintenance(owner, control, candidates, feedback, context, *, rng,
                         member_owners=None):
    """Called once by an actual leaf update, after its algorithm decision."""
    operation = owner.get_bound_operator("pool_maintenance")
    if operation is None or candidates is None or not len(candidates):
        return
    pool = getattr(control, "solution_pool", None)
    sink = _member_plans.get()
    if sink is None or sink[0] is not pool or not pool._in_attempt:
        raise RuntimeError("pool maintenance requires the owning Solver update transaction")
    items = getattr(feedback, "items", ())
    if len(items) != len(candidates):
        raise ValueError("pool maintenance requires aligned accepted feedback receipts")
    refs = []
    tokens = owner.candidate_tokens_for(control, candidates)
    for item, token in zip(items, tokens, strict=True):
        payload = item.info.get("accepted_solution_ref")
        if payload is None:
            raise ValueError("pool maintenance requires exact accepted_solution_ref")
        ref = SolutionRef.from_dict(payload)
        if ref.candidate_token != token:
            raise ValueError("pool maintenance receipt disagrees with its candidate token")
        refs.append(ref)
    refs = tuple(refs)
    members = _final_members(owner, control, refs) if member_owners is None else None
    partitions = {}
    if member_owners is not None:
        for name, child in member_owners:
            if name in partitions:
                raise ValueError("composite maintenance member owner paths must be unique")
            final = _final_members(child, control, refs)
            if final is not None:
                partitions[name] = (child, final)
    access = current_change_access()
    permissions = ({} if access is None else dict(allowed_refs=access.seed_refs,
        allowed_subpools=access.subpools, allow_main=access.allow_main))
    if access is not None and (members is not None or partitions):
        # Existing owned members are explicit inputs, not an unrestricted read
        # grant to the mother pool or to other algorithms' views.
        own_refs = (() if members is None else members[0])
        own_refs += tuple(ref for _, final in partitions.values() for ref in final[0])
        permissions["allowed_refs"] = (*access.seed_refs, *own_refs)
    from .pool_scope import working_pool_descriptor
    scope = ChangePool(pool, accepted_refs=refs,
                       working_pool=working_pool_descriptor(context), **permissions)
    try:
        objectives, violations = feedback
        lightweight = {key: value for key, value in context.items()
                       if isinstance(key, str) and (value is None or type(value) in (bool, int, float, str))}
        # A task may deliver projected selection feedback. Keep that explicit;
        # raw values remain available through accepted.raw_feedback().
        projection = getattr(feedback, "metadata", {}).get("subpool_projection")
        values = _detached_readonly(dict(objectives=np.asarray(objectives, dtype=float),
            violations=np.asarray(violations, dtype=float),
            parameters={"subpool_projection": projection}, context=lightweight))
        member_pools = {name: _feedback_pool(scope, *final, unit=getattr(child, "algorithm_unit", None))
                        for name, (child, final) in partitions.items()}
        final_pool = (None if members is None else _feedback_pool(scope, *members,
                      unit=getattr(owner, "algorithm_unit", None)))
        if member_owners is not None:
            final_pool = scope._selection(tuple(ref for view in member_pools.values() for ref in view.refs))
        request = PoolMaintenanceRequest(scope,
            _feedback_pool(scope, refs, values["objectives"], values["violations"]),
            values["objectives"], values["violations"], values["parameters"], values["context"],
            final_pool, None if member_owners is None else MappingProxyType(member_pools))
        with scope._writing("maintenance"):
            result = operation.maintain(request, rng=rng)
        automatic = tuple(scope._automatic_edits.values())
        if result is None and automatic:
            result = ()
        if not isinstance(result, (tuple, list)) or any(not isinstance(edit, PoolEdit) for edit in result):
            raise TypeError("pool maintenance must return an ordered sequence of PoolEdit plans")
        result = (*result, *automatic)
        # Validate while the owning access scope is still open. The collector
        # carries detached instructions only; no Pool view can escape this call.
        for edit in result:
            expected = scope.replace_members(edit.name, edit.members,
                                             create=bool(edit.expected.get("absent", False)))
            if expected.expected != edit.expected:
                raise ValueError("pool maintenance target identity or revision changed")
        sink[1].extend(result)
    finally:
        scope.close()


__all__ = ["PoolMaintenanceRequest"]
