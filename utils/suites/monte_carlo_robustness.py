"""
Monte Carlo + Robustness suite.

This is a recommended ("authority") combination:
- MonteCarloEvaluationPlugin provides stochastic evaluation statistics
- RobustnessBias consumes mc_std to penalize unstable candidates
"""

from __future__ import annotations

from typing import Any, Optional

from ..plugins import MonteCarloEvaluationPlugin, MonteCarloEvaluationConfig


def attach_monte_carlo_robustness(
    solver: Any,
    *,
    mc_samples: int = 16,
    reduce: str = "mean",
    cvar_alpha: float = 0.2,
    random_seed: Optional[int] = 0,
    robustness_weight: float = 0.1,
    robustness_aggregate: str = "mean",
    robustness_power: float = 1.0,
) -> Any:
    """
    Attach Monte Carlo evaluation + robustness bias to any solver base.

    The solver base stays pure: this function only wires plugin/bias.
    """
    from ...bias import BiasModule, RobustnessBias

    # Ensure bias module exists
    bias_module = getattr(solver, "bias_module", None)
    if bias_module is None:
        bias_module = BiasModule()
        setattr(solver, "bias_module", bias_module)
    setattr(solver, "enable_bias", True)

    # Add robustness bias (avoid duplicates)
    try:
        existing = getattr(bias_module, "get_bias", None)
        if callable(existing) and existing("robustness") is None:
            bias_module.add(
                RobustnessBias(
                    weight=float(robustness_weight),
                    aggregate=str(robustness_aggregate),
                    power=float(robustness_power),
                )
            )
    except Exception:
        bias_module.add(
            RobustnessBias(
                weight=float(robustness_weight),
                aggregate=str(robustness_aggregate),
                power=float(robustness_power),
            )
        )

    # Add MC plugin (avoid duplicates by name)
    cfg = MonteCarloEvaluationConfig(
        mc_samples=int(mc_samples),
        reduce=str(reduce),
        cvar_alpha=float(cvar_alpha),
        random_seed=random_seed,
    )
    plugin = MonteCarloEvaluationPlugin(config=cfg)
    pm = getattr(solver, "plugin_manager", None)
    if pm is not None and getattr(pm, "get", None) is not None:
        try:
            if pm.get(plugin.name) is None:
                solver.add_plugin(plugin)
        except Exception:
            solver.add_plugin(plugin)
    else:
        solver.add_plugin(plugin)

    return solver

