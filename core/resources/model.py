"""
Forwarding module for resources model.

This module re-exports from blackbase for seamless migration.
"""

from blackbase.resources import (
    DataRef,
    ResourceOffer,
    ResourceRequirement,
    WorkerDescriptor,
    TaskEnvelope,
    TaskResult,
    ScheduledTask,
)

__all__ = [
    "DataRef",
    "ResourceOffer",
    "ResourceRequirement",
    "WorkerDescriptor",
    "TaskEnvelope",
    "TaskResult",
    "ScheduledTask",
]