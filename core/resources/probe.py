"""
Forwarding module for probe utilities.

This module re-exports from blackbase for seamless migration.
"""

from blackbase.resources import (
    detect_total_memory_mb,
    detect_cuda_devices,
    detect_local_resource_offer,
    build_local_worker_descriptor,
)

__all__ = [
    "detect_total_memory_mb",
    "detect_cuda_devices",
    "detect_local_resource_offer",
    "build_local_worker_descriptor",
]