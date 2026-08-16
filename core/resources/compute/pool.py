"""
Forwarding module for the shared L0 compute pool.

PoolScheduler belongs to blackbase's shared Project/L0 substrate. nsgablack
keeps this import path only for compatibility.
"""

from __future__ import annotations

from blackbase.resources import (
    PoolResult,
    PoolScheduler,
    PoolTask,
    PoolTaskResult,
    ResourceOffer,
    ResourceRequirement,
    WorkerDescriptor,
    build_local_worker_descriptor,
    detect_local_resource_offer,
)


__all__ = [
    "WorkerDescriptor",
    "ResourceOffer",
    "ResourceRequirement",
    "build_local_worker_descriptor",
    "detect_local_resource_offer",
    "PoolScheduler",
    "PoolTask",
    "PoolResult",
    "PoolTaskResult",
]
