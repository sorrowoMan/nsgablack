from __future__ import annotations

from typing import Any, Callable, Optional


def component(
    *,
    kind: Optional[str] = None,
    key: Optional[str] = None,
    title: Optional[str] = None,
) -> Callable[[type], type]:
    """
    Mark a class as a catalog-registrable component.

    This marker is source-scanned by the UI registration flow. It does not
    change runtime behavior.
    """

    def _wrap(cls: type) -> type:
        setattr(cls, "__nsgablack_component__", True)
        if kind is not None:
            setattr(cls, "__nsgablack_component_kind__", str(kind))
        if key is not None:
            setattr(cls, "__nsgablack_component_key__", str(key))
        if title is not None:
            setattr(cls, "__nsgablack_component_title__", str(title))
        return cls

    return _wrap

