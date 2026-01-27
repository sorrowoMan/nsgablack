"""
Context helpers (canonical keys + minimal evaluation schema).

Recommended imports:
- `from nsgablack.utils.context import context_keys as CK`
- `from nsgablack.utils.context.context_schema import build_minimal_context`
"""

from __future__ import annotations

from . import context_keys
from .context_schema import MinimalEvaluationContext, build_minimal_context, validate_minimal_context

__all__ = [
    "context_keys",
    "MinimalEvaluationContext",
    "build_minimal_context",
    "validate_minimal_context",
]
