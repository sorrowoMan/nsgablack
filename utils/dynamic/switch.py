"""
Dynamic optimization switching base classes.

This module provides:
- SignalProviderBase: pluggable external signal readers.
- DynamicSwitchBase: plugin base for dynamic soft/hard switches.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional
from abc import ABC, abstractmethod
import time

from ...plugins.base import Plugin
from ..context.context_keys import KEY_DYNAMIC, KEY_GENERATION, KEY_PHASE_ID


@dataclass
class DynamicSwitchConfig:
    # How often to check signals (in generations)
    check_interval: int = 1

    # "auto" | "soft" | "hard" | "both"
    switch_mode: str = "auto"

    # Store signals under this key in context
    signal_key: str = KEY_DYNAMIC

    # Phase id key (also mirrored on solver.dynamic_phase_id)
    phase_key: str = KEY_PHASE_ID

    # Record switch events for audit
    record_history: bool = True


class SignalProviderBase(ABC):
    """External signal provider (sensor/API/CLI/etc.)."""

    @abstractmethod
    def read(self) -> Dict[str, Any]:
        """Return latest signal snapshot (dict)."""
        raise NotImplementedError

    def close(self) -> None:
        """Optional cleanup."""
        return None


class DynamicSwitchBase(Plugin, ABC):
    """
    Base plugin for dynamic optimization switches.

    Subclasses decide:
    - when to switch (should_switch)
    - how to switch (soft_switch/hard_switch)
    """
    context_requires = ()
    context_provides = (KEY_DYNAMIC, KEY_PHASE_ID)
    context_mutates = (KEY_DYNAMIC, KEY_PHASE_ID)
    context_cache = ()
    context_notes = (
        "Builds dynamic switch context and syncs solver dynamic phase/signals/events."
    )

    def __init__(
        self,
        name: str = "dynamic_switch",
        *,
        signal_provider: Optional[SignalProviderBase] = None,
        config: Optional[DynamicSwitchConfig] = None,
        priority: int = 0,
    ) -> None:
        super().__init__(name=name, priority=priority)
        self.signal_provider = signal_provider
        self.cfg = config or DynamicSwitchConfig()

        self.phase_id = 0
        self.last_switch_generation: Optional[int] = None
        self.last_signals: Dict[str, Any] = {}
        self.switch_events = []

    # ------------------------------------------------------------------
    # Hooks
    # ------------------------------------------------------------------
    def on_solver_init(self, solver) -> None:
        self._sync_solver_state(solver)

    def on_generation_start(self, generation: int) -> None:
        solver = getattr(self, "solver", None)
        if solver is None:
            return
        if int(self.cfg.check_interval) <= 0:
            return
        if (generation % int(self.cfg.check_interval)) != 0:
            return

        self._update_signals(solver)
        context = self._build_context(solver, generation)
        if not self.should_switch(solver, context):
            return

        mode = self._decide_mode(solver, context)
        self._apply_switch(solver, context, mode=mode)

    # ------------------------------------------------------------------
    # Abstract decisions
    # ------------------------------------------------------------------
    @abstractmethod
    def should_switch(self, solver, context: Dict[str, Any]) -> bool:
        """Return True if a switch should be applied."""
        raise NotImplementedError

    def select_switch_mode(self, solver, context: Dict[str, Any]) -> str:
        """Override to decide 'soft'/'hard'/'both' when switch_mode='auto'."""
        return "soft"

    def soft_switch(self, solver, context: Dict[str, Any]) -> None:
        """Override for soft switches (weights/params)."""
        return None

    def hard_switch(self, solver, context: Dict[str, Any]) -> None:
        """Override for hard switches (strategy swap/reset)."""
        return None

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------
    def _update_signals(self, solver) -> None:
        signals = {}
        if self.signal_provider is not None:
            try:
                signals = dict(self.signal_provider.read() or {})
            except Exception:
                signals = {}
        self.last_signals = signals
        setattr(solver, "dynamic_signals", signals)
        self._sync_solver_state(solver)

    def _build_context(self, solver, generation: int) -> Dict[str, Any]:
        ctx = {}
        try:
            if hasattr(solver, "build_context"):
                ctx = dict(solver.build_context())
        except Exception:
            ctx = {}
        ctx.setdefault(self.cfg.signal_key, dict(self.last_signals))
        ctx[self.cfg.phase_key] = int(self.phase_id)
        ctx[KEY_GENERATION] = int(generation)
        return ctx

    def _decide_mode(self, solver, context: Dict[str, Any]) -> str:
        mode = str(self.cfg.switch_mode).lower().strip()
        if mode in {"soft", "hard", "both"}:
            return mode
        return str(self.select_switch_mode(solver, context) or "soft").lower().strip()

    def _apply_switch(self, solver, context: Dict[str, Any], *, mode: str) -> None:
        if mode == "both":
            self.soft_switch(solver, context)
            self.hard_switch(solver, context)
        elif mode == "hard":
            self.hard_switch(solver, context)
        else:
            self.soft_switch(solver, context)

        self.phase_id += 1
        self.last_switch_generation = int(context.get(KEY_GENERATION, -1))
        self._sync_solver_state(solver)

        if self.cfg.record_history:
            weights = self._capture_strategy_weights(solver)
            self.switch_events.append(
                {
                    "phase_id": int(self.phase_id),
                    "generation": int(context.get(KEY_GENERATION, -1)),
                    "mode": mode,
                    "signals": dict(self.last_signals),
                    "strategy_weights": weights,
                    "timestamp": float(time.time()),
                }
            )

    def _sync_solver_state(self, solver) -> None:
        setattr(solver, "dynamic_phase_id", int(self.phase_id))
        setattr(solver, "dynamic_switch_events", list(self.switch_events))
        if not hasattr(solver, "dynamic_signals"):
            setattr(solver, "dynamic_signals", dict(self.last_signals))

    def _capture_strategy_weights(self, solver) -> Dict[str, Any]:
        adapter = getattr(solver, "adapter", None)
        weights = []
        if adapter is not None and hasattr(adapter, "strategies"):
            for spec in getattr(adapter, "strategies", []):
                weights.append(
                    {
                        "name": getattr(spec, "name", "strategy"),
                        "enabled": bool(getattr(spec, "enabled", True)),
                        "weight": float(getattr(spec, "weight", 1.0)),
                        "class": getattr(spec.adapter, "__class__", type(None)).__name__,
                    }
                )
        return weights

