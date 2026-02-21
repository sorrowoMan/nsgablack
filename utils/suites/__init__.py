"""
Authority suites (recommended combinations).

Suites are *optional* helpers that wire multiple extension points together
without polluting solver bases.
"""

from .monte_carlo_robustness import attach_monte_carlo_robustness
from .moead import attach_moead
from .simulated_annealing import attach_simulated_annealing
from .vns import attach_vns
from .multi_strategy import attach_multi_strategy_coop
from .benchmark_harness import attach_benchmark_harness
from .nsga2_engineering import attach_nsga2_engineering
from .module_report import attach_module_report
from .checkpoint_resume import attach_checkpoint_resume
from .ray_parallel import attach_ray_parallel
from .dynamic_switch import attach_dynamic_switch
from .async_event_driven import attach_async_event_driven
from .single_trajectory_adaptive import attach_single_trajectory_adaptive
from .trust_region_local import (
    attach_trust_region_dfo,
    attach_trust_region_subspace,
    attach_trust_region_subspace_learned,
    attach_trust_region_nonsmooth,
    attach_mas,
)
from .frontier_algorithms import (
    attach_trust_region_mo_dfo,
    attach_trust_region_subspace_frontier,
    attach_active_learning_surrogate,
    attach_robust_dfo,
    attach_surrogate_assisted_ea,
    attach_surrogate_model_lab,
    attach_structure_prior_mo,
    attach_multi_fidelity_eval,
    attach_risk_cvar,
)

__all__ = [
    "attach_monte_carlo_robustness",
    "attach_moead",
    "attach_simulated_annealing",
    "attach_vns",
    "attach_multi_strategy_coop",
    "attach_benchmark_harness",
    "attach_module_report",
    "attach_checkpoint_resume",
    "attach_nsga2_engineering",
    "attach_ray_parallel",
    "attach_dynamic_switch",
    "attach_async_event_driven",
    "attach_single_trajectory_adaptive",
    "attach_trust_region_dfo",
    "attach_trust_region_subspace",
    "attach_trust_region_subspace_learned",
    "attach_trust_region_nonsmooth",
    "attach_mas",
    "attach_trust_region_mo_dfo",
    "attach_trust_region_subspace_frontier",
    "attach_active_learning_surrogate",
    "attach_robust_dfo",
    "attach_surrogate_assisted_ea",
    "attach_surrogate_model_lab",
    "attach_structure_prior_mo",
    "attach_multi_fidelity_eval",
    "attach_risk_cvar",
]
