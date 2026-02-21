"""
Authority suite for simulated annealing (SA) adapter wiring.

Suites are optional helpers: they provide a "known good" combination without
polluting solver bases.
"""

from __future__ import annotations

from typing import Optional

from ...core.adapters import SAConfig, SimulatedAnnealingAdapter


def attach_simulated_annealing(
    solver,
    *,
    config: Optional[SAConfig] = None,
    **config_kwargs,
):
    """
    Attach SA adapter to a ComposableSolver-like solver.

    This suite only installs the adapter. RepresentationPipeline/mutator choices
    remain user-defined because they are problem/encoding dependent.
    """

    for meth in ("init_candidate", "mutate_candidate", "repair_candidate", "evaluate_population"):
        if not hasattr(solver, meth):
            raise ValueError(f"attach_simulated_annealing: solver missing required method: {meth}")

    cfg = config or SAConfig(**config_kwargs)
    adapter = SimulatedAnnealingAdapter(config=cfg)
    if not hasattr(solver, "set_adapter"):
        raise ValueError("attach_simulated_annealing: solver missing set_adapter()")
    solver.set_adapter(adapter)
    return adapter
