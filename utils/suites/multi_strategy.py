"""
Authority suite for multi-strategy cooperation (multi-algorithm parallelism).
"""

from __future__ import annotations

from typing import Optional, Sequence

from ...core.adapters import (
    AlgorithmAdapter,
    MultiStrategyConfig,
    MultiStrategyControllerAdapter,
    RoleSpec,
    StrategySpec,
)
from ...plugins import ParetoArchivePlugin


def attach_multi_strategy_coop(
    solver,
    *,
    strategies: Optional[Sequence[StrategySpec]] = None,
    roles: Optional[Sequence[RoleSpec]] = None,
    config: Optional[MultiStrategyConfig] = None,
    attach_pareto_archive: bool = True,
):
    """
    Attach MultiStrategyControllerAdapter to a ComposableSolver-like solver.

    - strategies: list of StrategySpec(adapter,name,weight,...)
    - roles: list of RoleSpec(name, adapter_factory, n_units, weight,...)
    - attach_pareto_archive: (optional) attach ParetoArchivePlugin for shared archive.
    """

    for meth in ("init_candidate", "mutate_candidate", "repair_candidate", "evaluate_population"):
        if not hasattr(solver, meth):
            raise ValueError(f"attach_multi_strategy_coop: solver missing required method: {meth}")

    if strategies is None and roles is None:
        raise ValueError("attach_multi_strategy_coop: provide strategies=... or roles=...")
    adapter = MultiStrategyControllerAdapter(strategies=strategies, roles=roles, config=config)
    if not hasattr(solver, "set_adapter"):
        raise ValueError("attach_multi_strategy_coop: solver missing set_adapter()")
    solver.set_adapter(adapter)

    if attach_pareto_archive and hasattr(solver, "add_plugin"):
        if getattr(solver, "get_plugin", None) is not None and solver.get_plugin("pareto_archive") is None:
            solver.add_plugin(ParetoArchivePlugin())
        elif getattr(solver, "get_plugin", None) is None:
            solver.add_plugin(ParetoArchivePlugin())

    return adapter

