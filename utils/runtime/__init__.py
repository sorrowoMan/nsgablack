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
from .sequence_graph import (
    SequenceGraphRecorder,
    build_sequence_token,
    record_sequence_event,
)
from .repro_bundle import (
    apply_bundle_to_solver,
    build_repro_bundle,
    compare_repro_bundle,
    load_repro_bundle,
    replay_spec,
    write_repro_bundle,
)

__all__ = []  # populated by star-imported modules
__all__.extend(
    [
        "DecisionReplayEngine",
        "append_decision_jsonl",
        "build_decision_event",
        "load_decision_jsonl",
        "record_decision_event",
        "SequenceGraphRecorder",
        "build_sequence_token",
        "record_sequence_event",
        "build_repro_bundle",
        "write_repro_bundle",
        "load_repro_bundle",
        "compare_repro_bundle",
        "apply_bundle_to_solver",
        "replay_spec",
    ]
)
