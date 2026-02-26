"""Decision trace schema and replay helpers."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, Iterator, List, Mapping, Optional
import json
import time


def _json_safe(value: Any) -> Any:
    try:
        import numpy as np  # type: ignore

        if isinstance(value, np.ndarray):
            return value.tolist()
        if isinstance(value, (np.integer, np.floating)):
            return value.item()
    except Exception:
        pass
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, Mapping):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_safe(v) for v in value]
    return str(value)


def build_decision_event(
    *,
    seq: int,
    event_type: str,
    component: str,
    decision: str,
    reason_code: str,
    generation: Optional[int] = None,
    step: Optional[int] = None,
    inputs: Optional[Mapping[str, Any]] = None,
    thresholds: Optional[Mapping[str, Any]] = None,
    evidence: Optional[Mapping[str, Any]] = None,
    outcome: Optional[Mapping[str, Any]] = None,
    run_id: Optional[str] = None,
) -> Dict[str, Any]:
    now = time.time()
    return {
        "seq": int(seq),
        "ts": float(now),
        "event_type": str(event_type),
        "component": str(component),
        "decision": str(decision),
        "reason_code": str(reason_code),
        "generation": int(generation) if generation is not None else None,
        "step": int(step) if step is not None else None,
        "inputs": _json_safe(dict(inputs or {})),
        "thresholds": _json_safe(dict(thresholds or {})),
        "evidence": _json_safe(dict(evidence or {})),
        "outcome": _json_safe(dict(outcome or {})),
        "run_id": str(run_id) if run_id is not None else None,
    }


def append_decision_jsonl(path: Path, event: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(dict(event), ensure_ascii=False) + "\n")


def load_decision_jsonl(path: Path) -> List[Dict[str, Any]]:
    if not path.is_file():
        return []
    rows: List[Dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        text = line.strip()
        if not text:
            continue
        try:
            obj = json.loads(text)
        except Exception:
            continue
        if isinstance(obj, dict):
            rows.append(obj)
    rows.sort(key=lambda x: int(x.get("seq", 0)))
    return rows


@dataclass
class DecisionReplayEngine:
    events: List[Dict[str, Any]]

    @classmethod
    def from_jsonl(cls, path: Path) -> "DecisionReplayEngine":
        return cls(events=load_decision_jsonl(path))

    def iter(
        self,
        *,
        until_seq: Optional[int] = None,
        event_type: Optional[str] = None,
        component: Optional[str] = None,
    ) -> Iterator[Dict[str, Any]]:
        for e in self.events:
            seq = int(e.get("seq", 0))
            if until_seq is not None and seq > int(until_seq):
                continue
            if event_type and str(e.get("event_type", "")) != str(event_type):
                continue
            if component and str(e.get("component", "")) != str(component):
                continue
            yield e

    def summary(self) -> Dict[str, Any]:
        by_type: Dict[str, int] = {}
        by_component: Dict[str, int] = {}
        for e in self.events:
            t = str(e.get("event_type", "unknown"))
            c = str(e.get("component", "unknown"))
            by_type[t] = int(by_type.get(t, 0)) + 1
            by_component[c] = int(by_component.get(c, 0)) + 1
        return {
            "count": int(len(self.events)),
            "event_type_counts": by_type,
            "component_counts": by_component,
            "first_seq": int(self.events[0].get("seq", 0)) if self.events else None,
            "last_seq": int(self.events[-1].get("seq", 0)) if self.events else None,
        }


def record_decision_event(
    solver: Any,
    *,
    event_type: str,
    component: str,
    decision: str,
    reason_code: str,
    inputs: Optional[Mapping[str, Any]] = None,
    thresholds: Optional[Mapping[str, Any]] = None,
    evidence: Optional[Mapping[str, Any]] = None,
    outcome: Optional[Mapping[str, Any]] = None,
) -> Optional[Dict[str, Any]]:
    """Record one semantic decision event via plugin sink when available."""
    sink = getattr(solver, "_decision_trace_sink", None)
    if callable(sink):
        try:
            return sink(
                event_type=event_type,
                component=component,
                decision=decision,
                reason_code=reason_code,
                inputs=inputs,
                thresholds=thresholds,
                evidence=evidence,
                outcome=outcome,
            )
        except Exception:
            return None
    return None
