"""Declare change destinations, then route exact admitted versions once.

These are optimization dataflow instructions. Evaluation, admission, and the
SolutionPool publication transaction stay owned by the existing control plane.
"""
from __future__ import annotations

from collections.abc import Mapping
from blackbase.wire import thaw_wire_mapping
from ..core.state.solution_pool import SolutionRef
from .change_pool import PoolEdit


def _target(pool, name, create):
    if pool is None:
        raise ValueError("change output requires a solution pool")
    if type(create) is not bool or not isinstance(name, str) or not name.strip():
        raise ValueError("change output requires a nonempty name and boolean create")
    descriptor = None
    if pool.has_subpool(name):
        metadata = pool.subpool_metadata(name)
        if metadata["kind"] != "candidate_collection":
            raise ValueError("change output must target an ordinary candidate_collection, not an algorithm view")
        if not metadata["published"]:
            raise ValueError("change output target must be committed before invocation")
        descriptor = pool.subpool_descriptor(name)
    elif not create:
        raise ValueError(f"change output subpool does not exist: {name}")
    return {"name": name, "create": create, "pool_id": pool.pool_id, "descriptor": descriptor}


def prepare_pool_outputs(pool, outputs):
    """Validate before evaluation; declaring a missing target never creates it."""
    return tuple(_target(pool, item.name, item.create) for item in outputs)


def _edit(pool, value, *, accepted_refs=()):
    if pool is None:
        raise ValueError("pool edit requires a solution pool")
    if not isinstance(value, Mapping) or set(value) != {"name", "members", "expected"}:
        raise ValueError("invalid change pool edit")
    value = thaw_wire_mapping(value)
    expected = PoolEdit._validate_expected(value["expected"])
    if expected["pool_id"] != pool.pool_id or expected["name"] != value["name"]:
        raise ValueError("pool edit target belongs to another pool or collection")
    absent = expected.get("absent", False)
    target = _target(pool, value["name"], absent)
    if (absent and target["descriptor"] is not None) or (not absent and target["descriptor"] != expected):
        raise ValueError("pool edit target identity or revision changed during the step")
    if not isinstance(value["members"], (list, tuple)):
        raise ValueError("pool edit members must be exact reference declarations")
    refs = tuple(SolutionRef.from_dict(dict(ref)) for ref in value["members"])
    accepted_refs = frozenset(accepted_refs)
    for ref in refs:
        if ref in accepted_refs:
            record = pool._record(ref, allow_pending=True)
            if record.stage != "accepted" or not pool._in_attempt:
                raise ValueError("pool maintenance requires this attempt's accepted members")
        else:
            pool.stamp_for(ref)  # Ordinary change plans still use committed data.
    return {"name": value["name"], "members": [ref.as_dict() for ref in refs], "expected": expected}


def prepare_pool_edits(pool, edits):
    return tuple(_edit(pool, edit.as_dict()) for edit in edits)


def publish_change_outputs(pool, refs, provenance, *, maintenance_edits=()):
    """Stage only accepted proposals; all writes join the pool's step transaction.

    Appending to a collection records admitted proposals, not the Adapter's
    final best/member choice. Existing view identity/revision is frozen at the
    invocation; replacing a same-named collection cannot redirect a proposal.
    """
    refs, provenance = tuple(refs), tuple(provenance)
    if len(refs) != len(provenance):
        raise ValueError("change outputs require aligned admitted references and provenance")
    planned = {}
    replacements = {}
    for plan in maintenance_edits:
        edit = _edit(pool, plan.as_dict(), accepted_refs=refs)
        name = edit["name"]
        if name in replacements and replacements[name] != edit:
            raise ValueError(f"conflicting replacements for the same pool: {name!r}")
        replacements[name] = edit
    for ref, record in zip(refs, provenance, strict=True):
        edits = record.metadata.get("change_pool_edits")
        if edits is not None:
            if not isinstance(edits, Mapping):
                raise ValueError("invalid change pool edit instruction")
            if edits.get("proposal_token") == record.candidate_token:
                if (edits.get("schema") != "nsgablack.change_pool_edits/v1"
                        or set(edits) != {"schema", "proposal_token", "edits"}
                        or record.candidate_token != ref.candidate_token
                        or not isinstance(edits["edits"], (list, tuple))):
                    raise ValueError("invalid change pool edit instruction")
                for raw_edit in edits["edits"]:
                    edit = _edit(pool, raw_edit)
                    name = edit["name"]
                    if name in replacements and replacements[name] != edit:
                        raise ValueError(f"conflicting replacements for the same pool: {name!r}")
                    replacements[name] = edit
        command = record.metadata.get("change_outputs")
        if command is None:
            continue
        if not isinstance(command, Mapping):
            raise ValueError("invalid change output instruction")
        # Inherited provenance is evidence, never a command for another token.
        if command.get("proposal_token") != record.candidate_token:
            continue
        if (command.get("schema") != "nsgablack.change_outputs/v1"
                or set(command) != {"schema", "proposal_token", "targets"}
                or record.candidate_token != ref.candidate_token
                or not isinstance(command["targets"], (list, tuple))):
            raise ValueError("invalid change output instruction")
        for target in command["targets"]:
            if not isinstance(target, Mapping) or set(target) != {"name", "create", "pool_id", "descriptor"}:
                raise ValueError("invalid change output target")
            target = thaw_wire_mapping(target)
            if target["pool_id"] != pool.pool_id:
                raise ValueError("change output target belongs to another pool")
            current = _target(pool, target["name"], target["create"])
            if current != dict(target):
                raise ValueError("change output target identity or revision changed during the step")
            name = target["name"]
            if name in planned:
                if planned[name][0] != dict(target):
                    raise ValueError(f"conflicting change output declarations: {name!r}")
                planned[name][1].append(ref)
            else:
                planned[name] = (dict(target), [ref])
    # Working areas receive only this step's accepted versions. They join the
    # same append plan rather than mutating the pool while children update.
    accepted = frozenset(refs)
    for name, (target, members) in getattr(maintenance_edits, "working_outputs", {}).items():
        if not set(members).issubset(accepted):
            raise ValueError("working_pool output exceeds this step's accepted versions")
        current = _target(pool, name, False)
        if current != target:
            raise ValueError("working_pool identity or revision changed during the step")
        if name in planned:
            if planned[name][0]["descriptor"] != current["descriptor"]:
                raise ValueError("conflicting working_pool output declarations")
            planned[name][1].extend(members)
        else:
            planned[name] = (current, list(members))
    if set(planned).intersection(replacements):
        names = sorted(set(planned).intersection(replacements))
        raise ValueError(f"a step cannot append and replace the same pool: {names!r}")
    # Validate the complete plan before the first membership write. An error in
    # any later control-plane operation still rolls all these memberships back.
    for name, (target, members) in planned.items():
        if target["descriptor"] is None:
            pool.create_subpool(name)
        pool.add_to_subpool(name, members)
    for name, edit in replacements.items():
        expected = edit["expected"]
        if expected.get("absent", False):
            # Build the ordinary collection in this same transaction. Accepted
            # versions are installed by the existing pending-aware row setter.
            pool.create_subpool(name)
            # Its public descriptor is intentionally unavailable until commit.
            # Absence was checked for the complete plan immediately above;
            # this freshly created destination is owned by this same write.
            expected = None
        pool.replace_subpool_members(name,
            tuple(SolutionRef.from_dict(ref) for ref in edit["members"]), expected=expected)
