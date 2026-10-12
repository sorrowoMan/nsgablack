"""Detached codec payloads; never traverse arbitrary runtime object graphs."""
from collections.abc import Mapping


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
