"""
Performance helpers (Numba-optional acceleration, memory management).

This namespace is for "speed/scale" utilities. It intentionally stays optional:
if you don't need it, ignore it.
"""

from __future__ import annotations

from .array_utils import validate_array_bounds
from .memory_manager import MemoryManager, OptimizationMemoryOptimizer, get_global_memory_manager
from .numba_helpers import NUMBA_AVAILABLE, fast_is_dominated, njit

try:
    from .fast_non_dominated_sort import FastNonDominatedSort, fast_non_dominated_sort_optimized
except Exception:
    # Keep performance namespace import-safe even when optional acceleration stack is broken.
    FastNonDominatedSort = None  # type: ignore

    def fast_non_dominated_sort_optimized(*args, **kwargs):  # type: ignore
        raise RuntimeError(
            "fast_non_dominated_sort_optimized is unavailable because optional "
            "acceleration dependencies failed to import."
        )

__all__ = [
    "validate_array_bounds",
    "FastNonDominatedSort",
    "fast_non_dominated_sort_optimized",
    "MemoryManager",
    "OptimizationMemoryOptimizer",
    "get_global_memory_manager",
    "NUMBA_AVAILABLE",
    "fast_is_dominated",
    "njit",
]
