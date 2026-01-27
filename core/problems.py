"""Deprecated module.

`core/problems.py` previously bundled benchmark/toy problems and demo helpers.
Those are not part of the stable Core promise and have been archived.

Prefer:
- `examples/` and `docs/cases/` for runnable, maintained workflows
- your own `BlackBoxProblem` implementations for real problems
"""

from __future__ import annotations

import warnings

warnings.warn(
    "nsgablack.core.problems is deprecated (toy/benchmark helpers are not part of core stability). "
    "Import from nsgablack.deprecated.legacy.core.problems if you really need the archived ones.",
    DeprecationWarning,
    stacklevel=2,
)

from ..deprecated.legacy.core.problems import *  # noqa: F401,F403

