"""Exact evaluated node receipts; graph costs remain Adapter-owned."""
from __future__ import annotations

import copy
import numpy as np

from ..pool_results import PoolRefinementState, PoolSelection
from ...units.contracts import candidate_array
from ...units.features import _signature


def project_root(control, candidate):
    """Deliver the seed's existing semantic identity before building a Unit."""
    lookup = getattr(control, "candidate_provenance_for", None)
    record = lookup(candidate) if callable(lookup) else None
    resolver = getattr(control, "semantic_candidate_state", None)
    binder = getattr(control, "bind_candidate_provenance", None)
    if record is None or not callable(resolver) or not callable(binder):
        return candidate
    semantic = resolver(candidate)
    binder((semantic,), (record,), activate=False)
    return semantic


def capture_receipt(control, candidates, feedback, index, score, violation):
    selected = PoolRefinementState().capture(control, candidates, feedback, index, score, violation)
    if selected.ref is None:
        return None  # Direct numerical Adapter calls do not invent pool evidence.
    value = {"selection": selected.as_dict(), "candidate": candidate_array(candidates[index]).tolist()}
    return {**value, "digest": _signature(value)}


def receipt_selection(receipt, *, candidate=None):
    if (not isinstance(receipt, dict) or set(receipt) != {"selection", "candidate", "digest"}
            or receipt["digest"] != _signature({key: receipt[key] for key in ("selection", "candidate")})):
        raise ValueError("graph pool receipt has invalid identity/content evidence")
    selected = PoolSelection.from_dict(receipt["selection"])
    if selected.ref is None:
        raise ValueError("graph pool receipt requires an exact accepted reference")
    if candidate is not None and not np.array_equal(
            candidate_array(candidate), np.asarray(receipt["candidate"]), equal_nan=True):
        raise ValueError("graph candidate differs from its exact pool receipt")
    return selected


def receipt_ref(receipt, control, *, candidate=None):
    if receipt is None:
        raise ValueError("graph candidate requires an exact pool reference; migrate legacy/manual search state")
    selected = receipt_selection(receipt, candidate=candidate)
    if control is not None:
        PoolRefinementState.validate(control, selected, candidate=np.asarray(receipt["candidate"]))
    return selected.ref


def derive_neighbor(control, candidate, parent_receipt, *, stage):
    if parent_receipt is None:
        return np.array(candidate_array(candidate), copy=True)
    selected = receipt_selection(parent_receipt)
    state = PoolRefinementState()
    state.current = selected
    return state.derive_candidate(control, candidate_array(candidate), stage=stage)


def validate_receipt_map(receipts, nodes, *, require=False):
    if not isinstance(receipts, dict) or set(receipts) != set(nodes):
        raise ValueError("graph node receipts must align with the live frontier/labels")
    for identity, receipt in receipts.items():
        if receipt is None:
            if require:
                raise ValueError("pool-root graph checkpoint requires exact node references")
        else:
            receipt_selection(receipt, candidate=nodes[identity].state)
    return copy.deepcopy(receipts)


def validate_pending_receipts(pending, *, require=False):
    """An expanded parent remains a root until all proposed edges settle."""
    if not isinstance(pending, list) or any(not isinstance(item, dict) for item in pending):
        raise ValueError("graph pending paths must be a list of mappings")
    for item in pending:
        if item.get("is_root"):
            if item.get("parent_id") is not None:
                raise ValueError("new graph root cannot inherit a parent path")
            continue
        receipt = item.get("parent_receipt")
        if receipt is not None:
            receipt_selection(receipt, candidate=item["parent_state"])
        elif require:
            raise ValueError("pool-root graph pending edge requires its exact parent reference")
