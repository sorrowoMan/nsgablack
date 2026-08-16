"""
Forwarding module for storage lease.

This module re-exports from blackbase for seamless migration.
"""

from blackbase.resources import (
    DataRef,
    ResourceContext,
    ResourceAudit,
    ResourceEvent,
    coerce_resource_context,
)

__all__ = [
    "DataRef",
    "ResourceContext",
    "ResourceAudit",
    "ResourceEvent",
    "coerce_resource_context",
]