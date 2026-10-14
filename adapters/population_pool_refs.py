"""Exact pool versions aligned by PopulationChange, never by numeric lookup.

The Adapter owns these bindings alongside its selection state. Custom Unit
builders keep their own member fields and codecs unchanged.
"""
from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy

import numpy as np
from blackbase.types import UnknownState

from ..core.state.solution_pool import SolutionRef
from ..units.features import _signature


def _semantic_binding_digest(ref, candidate_payload):
    # Include the exact version as well as its semantic content, so checkpoint
    # edits cannot silently swap a receipt while preserving a numeric digest.
    return _signature({"ref": ref.as_dict(), "candidate": candidate_payload})


def feedback_pool_bindings(control, candidates, feedback, tokens, *, candidate_metadata=None):
    items = getattr(feedback, "items", ())
    metadata = (tuple(candidate_metadata) if candidate_metadata is not None else
                tuple(dict(candidate.metadata) if isinstance(candidate, UnknownState) else {}
                      for candidate in candidates))
    if len(metadata) != len(candidates):
        raise ValueError("Population pool bindings require aligned candidate metadata")
    values = []
    refs, expected = [], []
    for index, (candidate, token) in enumerate(zip(candidates, tokens, strict=True)):
        payload = items[index].info.get("accepted_solution_ref") if items else None
        if payload is None:
            if items and getattr(control, "solution_pool", None) is not None:
                raise ValueError("Population feedback requires its exact accepted_solution_ref")
            values.append(None)  # Explicit non-pool/manual use remains supported.
            continue
        ref = SolutionRef.from_dict(payload)
        if ref.candidate_token != token:
            raise ValueError("Population pool reference disagrees with candidate token")
        numeric = candidate.as_array() if isinstance(candidate, UnknownState) else np.asarray(candidate, dtype=float)
        semantic = UnknownState(values=numeric, metadata=metadata[index]).as_dict()
        refs.append(ref)
        expected.append(semantic)
        values.append({"ref": ref.as_dict(), "candidate_digest": _signature(numeric),
                       "candidate_metadata": semantic["metadata"],
                       "semantic_digest": _semantic_binding_digest(ref, semantic)})
    if refs:
        pool = getattr(control, "solution_pool", None)
        if pool is None:
            raise ValueError("Population accepted receipts require their SolutionPool")
        batch = pool.read(refs, allow_pending=True)
        for ref, state, token, semantic in zip(refs, batch.semantic_states, batch.candidate_tokens, expected, strict=True):
            if token != ref.candidate_token or _signature(state.as_dict()) != _signature(semantic):
                raise ValueError("Population accepted receipt differs from candidate semantic content")
    return tuple(values)


def align_pool_bindings(previous, incoming, change):
    previous = tuple(previous) or (None,) * change.previous_count
    incoming = tuple(incoming)
    if len(previous) != change.previous_count or len(incoming) != change.incoming_count:
        raise ValueError("Population pool bindings do not align with member change")
    return tuple(deepcopy(previous[old] if old is not None else incoming[new])
                 for old, new in zip(change.previous_member_indices, change.incoming_member_indices, strict=True))


def validate_pool_bindings(bindings, population, tokens, *, control=None, require=False):
    count = 0 if population is None else len(population)
    values = tuple(bindings)
    if not values:
        values = (None,) * count
    if len(values) != count:
        raise ValueError("Population pool bindings do not align with population rows")
    tokens = tuple(tokens) or (None,) * count
    if len(tokens) != count:
        raise ValueError("Population pool bindings require aligned tokens")
    refs, indices = [], []
    for index, value in enumerate(values):
        if value is None:
            if require:
                raise ValueError("Live population requires exact pool versions; explicitly migrate legacy state")
            continue
        if (not isinstance(value, Mapping)
                or set(value) != {"ref", "candidate_digest", "candidate_metadata", "semantic_digest"}
                or not isinstance(value["candidate_metadata"], Mapping)):
            raise ValueError("Invalid population pool binding")
        ref = SolutionRef.from_dict(value["ref"])
        candidate = np.asarray(population[index], dtype=float)
        if ref.candidate_token != tokens[index] or value["candidate_digest"] != _signature(candidate):
            raise ValueError("Population pool binding token/content differs from its member")
        semantic = {"values": candidate.tolist(), "metadata": dict(value["candidate_metadata"])}
        if value["semantic_digest"] != _semantic_binding_digest(ref, semantic):
            raise ValueError("Population pool binding semantic content/reference differs from its member")
        refs.append(ref)
        indices.append(index)
    if control is not None and refs:
        # Resolve each backing record once, including repeated MOEA/D slots.
        batch = control.solution_pool.read(refs, allow_pending=True)
        if not np.array_equal(batch.numeric_matrix, np.asarray(population)[indices], equal_nan=True):
            raise ValueError("Population member differs from its exact pool version")
        for ref, state, token, index in zip(refs, batch.semantic_states, batch.candidate_tokens, indices, strict=True):
            if (token != tokens[index] or
                    values[index]["semantic_digest"] != _semantic_binding_digest(ref, state.as_dict())):
                raise ValueError("Population member semantic content differs from its exact pool version")
    return tuple(refs)


def publish_population_view(adapter, control):
    """Stage this mounted owner's evaluated members as one ordinary view.

    Publication reuses exact references; it neither copies candidates nor
    changes feedback interpretation. The pool transaction controls visibility.
    Standalone numeric/manual Adapter calls do not imply view publication.
    """
    pool = getattr(control, "solution_pool", None)
    root = getattr(control, "adapter", None)
    if pool is None or root is None:
        return
    pending, seen = [root], set()
    while pending:
        current = pending.pop()
        if id(current) in seen:
            continue
        seen.add(id(current))
        pending.extend(current.step_transaction_children())
    if id(adapter) not in seen:
        return
    from .subpools import adapter_path
    creator = adapter_path(root, adapter)
    name = "/".join((*creator, "population"))
    bindings = adapter._population_pool_bindings
    if not bindings or any(value is None for value in bindings):
        # A manual update can lose receipts after an earlier full publication.
        # Withdraw only our native view; the pool transaction rolls this back
        # with the Unit if the surrounding attempt fails.
        if pool.has_subpool(name):
            metadata = pool.subpool_metadata(name)
            if metadata["kind"] == "candidate_view" and tuple(metadata["created_by"] or ()) == creator:
                pool.drop_subpool(name)
        return
    adapter.algorithm_unit.require_current_feedback()
    refs = adapter.get_solution_pool_roots(control)
    if refs:
        pool.publish_subpool_view(name, refs, created_by=creator)


def validate_numeric_population_replacement(bindings, *, preserve_tokens):
    """Numerical setters cannot discard already-owned pool identities."""
    if not preserve_tokens and any(value is not None for value in bindings):
        raise ValueError("Replacing pool-bound population members requires explicit pool input; "
                         "the numeric snapshot setter only supports same-member feedback refresh")
