"""
Authority suite for async event-driven orchestration.
"""

from __future__ import annotations

from typing import Optional, Sequence

from ...core.adapters import AsyncEventDrivenAdapter, AsyncEventDrivenConfig, EventStrategySpec
from ...plugins import AsyncEventHubConfig, AsyncEventHubPlugin, ParetoArchivePlugin


def attach_async_event_driven(
    solver,
    *,
    strategies: Sequence[EventStrategySpec],
    config: Optional[AsyncEventDrivenConfig] = None,
    attach_async_hub: bool = True,
    async_hub_config: Optional[AsyncEventHubConfig] = None,
    attach_pareto_archive: bool = True,
):
    """
    Attach AsyncEventDrivenAdapter and optional runtime companions.

    Required solver capabilities:
    - set_adapter()/adapter assignment
    - add_plugin()
    - init_candidate/mutate_candidate/repair_candidate/evaluate_population
    """

    for meth in ("init_candidate", "mutate_candidate", "repair_candidate", "evaluate_population"):
        if not hasattr(solver, meth):
            raise ValueError(f"attach_async_event_driven: solver missing required method: {meth}")

    adapter = AsyncEventDrivenAdapter(strategies=strategies, config=config)
    if not hasattr(solver, "set_adapter"):
        raise ValueError("attach_async_event_driven: solver missing set_adapter()")
    solver.set_adapter(adapter)

    if attach_async_hub and hasattr(solver, "add_plugin"):
        existing = solver.get_plugin("async_event_hub") if hasattr(solver, "get_plugin") else None
        if existing is None:
            solver.add_plugin(AsyncEventHubPlugin(cfg=async_hub_config))

    if attach_pareto_archive and hasattr(solver, "add_plugin"):
        existing = solver.get_plugin("pareto_archive") if hasattr(solver, "get_plugin") else None
        if existing is None:
            solver.add_plugin(ParetoArchivePlugin())

    return adapter
