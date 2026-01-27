"""Legacy re-export for role-based adapter composition.

Canonical path: `nsgablack.core.adapters`.

This module exists for a transition period only.
"""

import warnings

warnings.warn(
    "`nsgablack.core.role_adapters` is deprecated; use `nsgablack.core.adapters` instead.",
    DeprecationWarning,
    stacklevel=2,
)

from .adapters.role_adapters import RoleAdapter, MultiRoleControllerAdapter

__all__ = ["RoleAdapter", "MultiRoleControllerAdapter"]
