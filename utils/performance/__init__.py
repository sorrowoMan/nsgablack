"""
Performance helpers (Numba-optional acceleration, memory management).

This namespace is for "speed/scale" utilities. It intentionally stays optional:
if you don't need it, ignore it.
"""

from __future__ import annotations

from .array_utils import validate_array_bounds
from .fast_non_dominated_sort import FastNonDominatedSort, fast_non_dominated_sort_optimized
from .memory_manager import MemoryManager, OptimizationMemoryOptimizer, get_global_memory_manager
from .numba_helpers import NUMBA_AVAILABLE, fast_is_dominated, njit

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
