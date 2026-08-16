"""Forwarding module for context contracts (legacy path).

This module re-exports from blackbase for seamless migration.
Prefer importing from nsgablack.core.state.context_contracts or blackbase.context.
"""

from blackbase.context import (
    ContextContract,
    collect_solver_contracts,
    detect_context_conflicts,
    get_component_contract,
    validate_context_contracts,
)

__all__ = [
    "ContextContract",
    "collect_solver_contracts",
    "detect_context_conflicts",
    "get_component_contract",
    "validate_context_contracts",
]
