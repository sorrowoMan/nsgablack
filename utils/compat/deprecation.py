"""Unified deprecation warnings for legacy APIs.

This module is intentionally tiny and dependency-free.
Use it in compat re-exports so users get consistent, searchable warnings.
"""

from __future__ import annotations

from typing import Optional
import warnings


def warn_deprecated(
    old: str,
    *,
    new: Optional[str] = None,
    remove_in: Optional[str] = None,
    extra: Optional[str] = None,
    stacklevel: int = 2,
) -> None:
    parts = [f"{old} 已弃用"]
    if new:
        parts.append(f"请改用 {new}")
    if remove_in:
        parts.append(f"计划在 {remove_in} 移除")
    if extra:
        parts.append(str(extra).strip())
    msg = "；".join([p for p in parts if p])
    warnings.warn(msg, DeprecationWarning, stacklevel=max(1, int(stacklevel)))

