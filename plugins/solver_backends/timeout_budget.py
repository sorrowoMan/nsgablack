from __future__ import annotations

from dataclasses import dataclass
import time
from typing import Any, Dict, Mapping, Optional

from ..base import Plugin


@dataclass
class TimeoutBudgetConfig:
    layer: str = "L2"
    max_calls: int = 1000
    time_budget_ms: float = 60_000.0
    fail_closed: bool = True


class TimeoutBudgetPlugin(Plugin):
    """Budget guard for inner solver calls."""

    is_algorithmic = False
    context_requires = ()
    context_provides = ()
    context_mutates = ()
    context_cache = ()
    context_notes = (
        "Guards inner-solver calls by max_calls/time_budget; "
        "blocks execution through on_inner_guard.",
    )

    def __init__(
        self,
        name: str = "inner_timeout_budget",
        *,
        config: Optional[TimeoutBudgetConfig] = None,
        priority: int = 90,
    ) -> None:
        super().__init__(name=name, priority=priority)
        self.cfg = config or TimeoutBudgetConfig()
        self._t0 = 0.0
        self._calls = 0
        self._blocked = 0
        self._last_reason = ""

    def on_solver_init(self, solver):
        _ = solver
        self._t0 = time.perf_counter()
        self._calls = 0
        self._blocked = 0
        self._last_reason = ""
        return None

    def on_inner_guard(self, solver, eval_ctx: Mapping[str, Any]):
        _ = solver
        layer = str(eval_ctx.get("source_layer", "L2"))
        if layer != str(self.cfg.layer):
            return {"allow": True, "reason": "layer-mismatch"}

        elapsed_ms = (time.perf_counter() - self._t0) * 1000.0
        if self._calls >= int(self.cfg.max_calls):
            self._blocked += 1
            self._last_reason = "max-calls"
            return {"allow": not self.cfg.fail_closed, "reason": "max-calls"}
        if elapsed_ms > float(self.cfg.time_budget_ms):
            self._blocked += 1
            self._last_reason = "time-budget"
            return {"allow": not self.cfg.fail_closed, "reason": "time-budget"}
        return {"allow": True, "reason": "ok"}

    def on_inner_result(self, solver, packet: Mapping[str, Any]):
        _ = solver
        layer = str(packet.get("source_layer", "L2"))
        if layer == str(self.cfg.layer):
            self._calls += 1
        return None

    def get_report(self) -> Optional[Dict[str, Any]]:
        out = super().get_report() or {}
        out["layer"] = self.cfg.layer
        out["max_calls"] = int(self.cfg.max_calls)
        out["time_budget_ms"] = float(self.cfg.time_budget_ms)
        out["calls"] = int(self._calls)
        out["blocked"] = int(self._blocked)
        out["last_reason"] = self._last_reason
        return out
