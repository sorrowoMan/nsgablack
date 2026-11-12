"""
Performance helpers (Numba-optional acceleration, memory management).

This namespace is for "speed/scale" utilities. It intentionally stays optional:
if you don't need it, ignore it.
"""

from __future__ import annotations

from importlib import import_module

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


_EXPORTS = {
    "validate_array_bounds": "array_utils",
    "FastNonDominatedSort": "fast_non_dominated_sort",
    "fast_non_dominated_sort_optimized": "fast_non_dominated_sort",
    "MemoryManager": "memory_manager",
    "OptimizationMemoryOptimizer": "memory_manager",
    "get_global_memory_manager": "memory_manager",
    "NUMBA_AVAILABLE": "numba_helpers", "fast_is_dominated": "numba_helpers", "njit": "numba_helpers",
}


def __getattr__(name):
    module = _EXPORTS.get(name)
    if module is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    value = getattr(import_module(f"{__name__}.{module}"), name)
    globals()[name] = value
    return value


def __dir__():
    return sorted(set(globals()) | set(__all__))
