"""Detached codec payloads; never traverse arbitrary runtime object graphs."""
from collections.abc import Mapping
import numpy as np
from blackbase.types import UnknownState


def detach_codec_payload(value, *, path="payload"):
    """Copy only the closed JSON data model, with precise invalid-value paths.

    Numeric infinities retain Python JSON's existing numeric convention. Codecs
    must tag richer values (arrays, tuple keys, bytes, semantic states) themselves.
    """
    active = set()

    def visit(item, location):
        if item is None or type(item) in (str, bool, int, float):
            return item
        if isinstance(item, (Mapping, list)):
            identity = id(item)
            if identity in active:
                raise TypeError(f"Unit codec {location} contains a cycle")
            active.add(identity)
            try:
                if isinstance(item, Mapping):
                    if any(type(key) is not str for key in item):
                        raise TypeError(f"Unit codec {location} requires string keys")
                    return {k: visit(v, f"{location}.{k}") for k, v in item.items()}
                return [visit(v, f"{location}[{i}]") for i, v in enumerate(item)]
            finally:
                active.remove(identity)
        raise TypeError(f"Unit codec {location} cannot persist {type(item).__name__}; use an explicit data codec")

    if not isinstance(value, Mapping):
        raise TypeError(f"Unit codec {path} must be a Mapping")
    return visit(value, path)


def detach_step_value(value, *, path="step", _active=None, _depth=0):
    """Private rollback data, preserving native arrays without copying services.

    Unlike a checkpoint this value never crosses a process/storage boundary.
    Capture and restore each copy arrays; repeat restores cannot mutate the baseline.
    """
    if _depth > 128:
        raise TypeError(f"Unit {path} exceeds step snapshot depth limit")
    if value is None or type(value) in (str, bool, int, float, bytes):
        return value
    if isinstance(value, np.ndarray):
        if value.dtype.kind not in "biuf":
            raise TypeError(f"Unit {path} arrays must be real numeric")
        if value.dtype.metadata:
            raise TypeError(f"Unit {path} cannot capture ndarray dtype metadata")
        return np.array(value, copy=True, subok=False)
    if isinstance(value, np.generic):
        return detach_step_value(value.item(), path=path, _active=_active, _depth=_depth+1)
    if isinstance(value, UnknownState):
        return UnknownState.from_protocol_payload(detach_codec_payload(value.as_dict()))
    if not isinstance(value, (Mapping, list, tuple)):
        raise TypeError(f"Unit {path} cannot capture runtime object {type(value).__name__}")
    active = set() if _active is None else _active
    identity = id(value)
    if identity in active:
        raise TypeError(f"Unit {path} contains a cycle")
    active.add(identity)
    try:
        def copy_child(item, location):
            return detach_step_value(item, path=location, _active=active, _depth=_depth+1)
        if isinstance(value, Mapping):
            return {copy_child(key, path+".<key>"): copy_child(item, path+f"[{key!r}]")
                    for key, item in value.items()}
        items = [copy_child(item, path+f"[{i}]") for i, item in enumerate(value)]
        return tuple(items) if isinstance(value, tuple) else items
    finally:
        active.remove(identity)
