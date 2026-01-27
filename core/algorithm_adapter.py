"""Legacy re-export for adapter APIs.

Canonical path: `nsgablack.core.adapters`.

This module exists for a transition period only.
"""

import warnings

warnings.warn(
    "`nsgablack.core.algorithm_adapter` is deprecated; use `nsgablack.core.adapters` instead.",
    DeprecationWarning,
    stacklevel=2,
)

from .adapters.algorithm_adapter import AlgorithmAdapter, CompositeAdapter

__all__ = ["AlgorithmAdapter", "CompositeAdapter"]
