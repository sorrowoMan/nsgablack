"""
Authority suite for single-trajectory adaptive search.
"""

from __future__ import annotations

from typing import Optional

from ...core.adapters import SingleTrajectoryAdaptiveAdapter, SingleTrajectoryAdaptiveConfig


def attach_single_trajectory_adaptive(
    solver,
    *,
    config: Optional[SingleTrajectoryAdaptiveConfig] = None,
):
    """
    Attach SingleTrajectoryAdaptiveAdapter to a ComposableSolver-like solver.
    """

    for meth in ("init_candidate", "mutate_candidate", "repair_candidate", "evaluate_population"):
        if not hasattr(solver, meth):
            raise ValueError(f"attach_single_trajectory_adaptive: solver missing required method: {meth}")

    adapter = SingleTrajectoryAdaptiveAdapter(config=config)
    if not hasattr(solver, "set_adapter"):
        raise ValueError("attach_single_trajectory_adaptive: solver missing set_adapter()")
    solver.set_adapter(adapter)
    return adapter
