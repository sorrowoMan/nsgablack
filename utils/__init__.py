"""
Utilities namespace.

Design:
- Keep `import nsgablack.utils` cheap (no heavy imports, no optional deps).
- Provide "category entrypoints" (subpackages) for discoverability.
- Keep older flat imports working via lazy re-exports + DeprecationWarning.

Recommended:
- Use `python -m nsgablack catalog search <keyword>` to locate the canonical path.
"""

from __future__ import annotations

from importlib import import_module

__all__ = [
    # Category entrypoints (recommended)
    "analysis",
    "constraints",
    "context",
    "engineering",
    "parallel",
    "performance",
    "plugins",
    "runs",
    "runtime",
    "suites",
    "surrogate",
    "viz",
]


def __getattr__(name):
    if name in {
        "analysis",
        "constraints",
        "context",
        "engineering",
        "parallel",
        "performance",
        "plugins",
        "runs",
        "runtime",
        "suites",
        "surrogate",
        "viz",
    }:
        return import_module(f"{__name__}.{name}")
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")
