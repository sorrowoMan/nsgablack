"""Phase-based surrogate control bias."""
from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional

from .base import SurrogateControlBias


class PhaseScheduleBias(SurrogateControlBias):
    """Switch surrogate configs by phase."""
    context_requires = ()
    context_provides = ()
    context_mutates = ()
    context_cache = ()
    context_notes = "No explicit context dependency; outputs scalar bias only."



    def __init__(
        self,
        phases: Iterable[Dict[str, Any]],
        use_ratio: bool = True,
        default_phase: Optional[Dict[str, Any]] = None,
        name: str = "phase_schedule",
    ):
        super().__init__(name=name)
        self.use_ratio = bool(use_ratio)
        self.phases = self._normalize_phases(phases)
        self.default_phase = default_phase

    def apply(self, context: Any) -> Dict[str, Any]:
        value = self._progress_value(context)
        phase = self._select_phase(value)
        if phase is None:
            return {}
        return self._extract_updates(phase)

    def _progress_value(self, context: Any) -> float:
        if self.use_ratio:
            if hasattr(context, "progress"):
                return float(context.progress)
            try:
                generation = float(getattr(context, "generation", 0.0))
                max_generations = float(getattr(context, "max_generations", 1.0))
                if max_generations <= 0:
                    return 0.0
                return generation / max_generations
            except Exception:
                return 0.0
        try:
            return float(getattr(context, "generation", 0.0))
        except Exception:
            return 0.0

    def _normalize_phases(self, phases: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
        normalized = []
        for phase in phases or []:
            if not isinstance(phase, dict):
                continue
            start = phase.get("start", 0.0)
            end = phase.get("end", None)
            data = dict(phase)
            data["start"] = float(start) if start is not None else 0.0
            data["end"] = float(end) if end is not None else None
            normalized.append(data)
        normalized.sort(key=lambda item: item.get("start", 0.0))
        return normalized

    def _select_phase(self, value: float) -> Optional[Dict[str, Any]]:
        for phase in self.phases:
            start = phase.get("start", 0.0)
            end = phase.get("end", None)
            if end is None:
                if value >= start:
                    return phase
            else:
                if start <= value < end:
                    return phase
        return self.default_phase

    def _extract_updates(self, phase: Dict[str, Any]) -> Dict[str, Any]:
        if "updates" in phase and isinstance(phase["updates"], dict):
            return dict(phase["updates"])
        updates = {}
        for key, value in phase.items():
            if key in ("name", "start", "end"):
                continue
            updates[key] = value
        return updates
