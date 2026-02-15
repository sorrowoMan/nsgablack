"""
Concrete dynamic switch plugin with functional callbacks.
"""

from __future__ import annotations

from typing import Any, Callable, Dict, Optional

from ...utils.dynamic import DynamicSwitchBase, DynamicSwitchConfig, SignalProviderBase


class DynamicSwitchPlugin(DynamicSwitchBase):
    context_requires = ()
    context_provides = ("dynamic", "phase_id")
    context_mutates = ("dynamic", "phase_id")
    context_cache = ()
    context_notes = (
        "Builds runtime switch context with dynamic signals and phase id; "
        "applies soft/hard switch callbacks and syncs solver dynamic state."
    )
    """
    Concrete dynamic switch plugin using user-provided callbacks.

    Callbacks:
    - should_switch_fn(solver, context) -> bool
    - soft_switch_fn(solver, context) -> None (optional)
    - hard_switch_fn(solver, context) -> None (optional)
    - select_mode_fn(solver, context) -> "soft"|"hard"|"both" (optional)
    """

    def __init__(
        self,
        *,
        should_switch_fn: Callable[[Any, Dict[str, Any]], bool],
        soft_switch_fn: Optional[Callable[[Any, Dict[str, Any]], None]] = None,
        hard_switch_fn: Optional[Callable[[Any, Dict[str, Any]], None]] = None,
        select_mode_fn: Optional[Callable[[Any, Dict[str, Any]], str]] = None,
        signal_provider: Optional[SignalProviderBase] = None,
        config: Optional[DynamicSwitchConfig] = None,
        name: str = "dynamic_switch",
        priority: int = 0,
    ) -> None:
        super().__init__(name=name, signal_provider=signal_provider, config=config, priority=priority)
        self._should_switch_fn = should_switch_fn
        self._soft_switch_fn = soft_switch_fn
        self._hard_switch_fn = hard_switch_fn
        self._select_mode_fn = select_mode_fn

    def should_switch(self, solver, context: Dict[str, Any]) -> bool:
        return bool(self._should_switch_fn(solver, context))

    def select_switch_mode(self, solver, context: Dict[str, Any]) -> str:
        if self._select_mode_fn is None:
            return super().select_switch_mode(solver, context)
        return str(self._select_mode_fn(solver, context))

    def soft_switch(self, solver, context: Dict[str, Any]) -> None:
        if self._soft_switch_fn is None:
            return None
        return self._soft_switch_fn(solver, context)

    def hard_switch(self, solver, context: Dict[str, Any]) -> None:
        if self._hard_switch_fn is None:
            return None
        return self._hard_switch_fn(solver, context)
