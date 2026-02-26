"""
Runtime helpers (dependency detection / safe optional imports).
"""

from __future__ import annotations

from .dependencies import *  # noqa: F403
from .imports import *  # noqa: F403
from .decision_trace import (
    DecisionReplayEngine,
    append_decision_jsonl,
    build_decision_event,
    load_decision_jsonl,
    record_decision_event,
)

__all__ = []  # populated by star-imported modules
__all__.extend(
    [
        "DecisionReplayEngine",
        "append_decision_jsonl",
        "build_decision_event",
        "load_decision_jsonl",
        "record_decision_event",
    ]
)
