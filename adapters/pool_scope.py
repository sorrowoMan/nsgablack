"""Lightweight working-area bindings for existing composite Adapter calls.

Only a committed collection descriptor crosses a call boundary. Candidate
storage, input queues and publication remain owned by the existing pool.
"""
from __future__ import annotations

from collections.abc import Mapping

from nsgablack.context_keys import KEY_SOLUTION_WORKING_POOL
from ..core.state.solution_pool import SolutionPool, SolutionRef


KEY_WORKING_POOL = KEY_SOLUTION_WORKING_POOL


def validate_working_pool_name(name):
    if name is not None and (not isinstance(name, str) or not name.strip()):
        raise ValueError("working_pool must be a nonempty public collection name or None")
    return name


def working_pool_descriptor(context):
    value = (context or {}).get(KEY_WORKING_POOL)
    return None if value is None else SolutionPool.validate_subpool_descriptor(value)


def _validate_binding(pool, descriptor):
    if not isinstance(pool, SolutionPool):
        raise TypeError("working_pool requires the control plane's SolutionPool")
    descriptor = SolutionPool.validate_subpool_descriptor(descriptor)
    if descriptor["pool_id"] != pool.pool_id:
        raise ValueError("working_pool binding belongs to another SolutionPool")
    name = descriptor["name"]
    if not pool.has_subpool(name):
        raise ValueError(f"working_pool does not exist: {name!r}")
    metadata = pool.subpool_metadata(name)
    if metadata["kind"] != "candidate_collection" or not metadata["published"]:
        raise ValueError("working_pool must be an existing committed ordinary candidate_collection")
    if pool.subpool_descriptor(name) != descriptor:
        raise ValueError("working_pool identity or revision changed during the proposal")
    return descriptor


def bind_working_pool(control, context, name, *, previous=None):
    """Bind a public name, or inherit the enclosing call's exact descriptor."""
    validate_working_pool_name(name)
    result = dict(context or {})
    pool = getattr(control, "solution_pool", None)
    inherited = working_pool_descriptor(result)
    if inherited is not None:
        _validate_binding(pool, inherited)
    if name is not None:
        if not isinstance(pool, SolutionPool) or not pool.has_subpool(name):
            raise ValueError(f"working_pool does not exist: {name!r}")
        inherited = _validate_binding(pool, pool.subpool_descriptor(name))
    if previous is not None:
        previous = SolutionPool.validate_subpool_descriptor(previous)
        if inherited is None or any(previous[key] != inherited[key]
                                     for key in ("pool_id", "name", "view_id")):
            raise ValueError("working_pool identity changed between proposals")
    if inherited is not None:
        result[KEY_WORKING_POOL] = inherited
    return result


def restore_working_pool_context(original, current):
    """Merge observations without rebinding the original proposal's workspace."""
    result = dict(original or {})
    result.update(current or {})
    descriptor = working_pool_descriptor(original)
    if descriptor is None:
        result.pop(KEY_WORKING_POOL, None)
    else:
        result[KEY_WORKING_POOL] = descriptor
    return result


def working_pool_source(pool, context):
    descriptor = working_pool_descriptor(context)
    return None if descriptor is None else _validate_binding(pool, descriptor)["name"]


def stage_working_pool_results(owner, control, candidates, feedback, context):
    """Claim this update's accepted versions for their nearest working area.

    Children run first, so an explicit inner area claims its own results before
    a surrounding composite handles the rest. No membership is changed here.
    """
    descriptor = working_pool_descriptor(context)
    if descriptor is None or candidates is None or not len(candidates):
        return
    pool = getattr(control, "solution_pool", None)
    _validate_binding(pool, descriptor)
    items = getattr(feedback, "items", ())
    if not isinstance(items, (tuple, list)):
        raise TypeError("working_pool publication requires accepted feedback receipts")
    tokens = tuple(owner.candidate_tokens_for(control, candidates))
    if len(items) != len(tokens):
        raise ValueError("working_pool receipts must align with the accepted candidates")
    refs = []
    for item, token in zip(items, tokens, strict=True):
        payload = item.info.get("accepted_solution_ref")
        if not isinstance(payload, Mapping):
            raise ValueError("working_pool requires exact accepted_solution_ref receipts")
        ref = SolutionRef.from_dict(dict(payload))
        if ref.candidate_token != token:
            raise ValueError("working_pool receipt differs from its candidate token")
        record = pool._record(ref, allow_pending=True)
        if record.stage != "accepted" or not pool._in_attempt:
            raise ValueError("working_pool requires this attempt's admitted versions")
        refs.append(ref)
    from .pool_maintenance import collect_working_pool_results
    collect_working_pool_results(pool, descriptor, refs)


__all__ = []
