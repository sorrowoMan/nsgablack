"""
Suite helper for dynamic switching.
"""

from __future__ import annotations

from typing import Any, Callable, Dict, Optional

from ...plugins import DynamicSwitchPlugin
from ..dynamic import DynamicSwitchConfig, SignalProviderBase


def attach_dynamic_switch(
    solver: Any,
    *,
    plugin: Optional[DynamicSwitchPlugin] = None,
    should_switch_fn: Optional[Callable[[Any, Dict[str, Any]], bool]] = None,
    soft_switch_fn: Optional[Callable[[Any, Dict[str, Any]], None]] = None,
    hard_switch_fn: Optional[Callable[[Any, Dict[str, Any]], None]] = None,
    select_mode_fn: Optional[Callable[[Any, Dict[str, Any]], str]] = None,
    signal_provider: Optional[SignalProviderBase] = None,
    config: Optional[DynamicSwitchConfig] = None,
) -> Any:
    """
    Attach a dynamic switch plugin (base for dynamic optimization).

    - Provide `plugin` directly, OR
    - Provide callback functions to construct a DynamicSwitchPlugin.
    """
    if plugin is None:
        if should_switch_fn is None:
            raise ValueError("attach_dynamic_switch requires plugin or should_switch_fn")
        plugin = DynamicSwitchPlugin(
            should_switch_fn=should_switch_fn,
            soft_switch_fn=soft_switch_fn,
            hard_switch_fn=hard_switch_fn,
            select_mode_fn=select_mode_fn,
            signal_provider=signal_provider,
            config=config,
        )
    solver.add_plugin(plugin)
    return solver

