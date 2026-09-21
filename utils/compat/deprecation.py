"""Shared deprecation warning helpers."""

from __future__ import annotations

import warnings


def warn_deprecated(
    *,
    old: str,
    new: str,
    remove_in: str,
    stacklevel: int = 2,
) -> None:
    """Emit the API stability policy's machine-readable migration warning."""
    warnings.warn(
        f"old={old}; new={new}; remove_in={remove_in}",
        DeprecationWarning,
        stacklevel=stacklevel,
    )


__all__ = ["warn_deprecated"]
