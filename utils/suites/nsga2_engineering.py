"""
Suite: NSGA-II engineering defaults.

Goal: keep `core/` pure (no implicit capability wiring) while still providing a
one-liner that users can rely on to avoid "漏配".
"""

from __future__ import annotations

from typing import Any


def attach_nsga2_engineering(
    solver: Any,
    *,
    enable_basic_elite: bool = True,
    enable_convergence: bool = False,
    enable_diversity_metrics: bool = False,
    convergence_early_stop: bool = False,
) -> Any:
    """
    Attach a conservative set of plugins to a `EvolutionSolver`.

    Notes
    - This suite intentionally does *not* change representation/bias choices.
    - Plugins are optional; toggle them by flags.
    """

    if enable_basic_elite:
        from ...plugins.runtime.elite_retention import BasicElitePlugin

        solver.add_plugin(BasicElitePlugin(retention_prob=0.9, retention_ratio=0.1))

    if enable_convergence:
        from ...plugins.runtime.convergence import ConvergencePlugin

        solver.add_plugin(ConvergencePlugin(enable_early_stop=bool(convergence_early_stop)))

    if enable_diversity_metrics:
        from ...plugins.runtime.diversity_init import DiversityInitPlugin

        solver.add_plugin(DiversityInitPlugin())

    return solver



