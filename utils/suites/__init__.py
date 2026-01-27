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
from .ray_parallel import attach_ray_parallel

__all__ = [
    "attach_monte_carlo_robustness",
    "attach_moead",
    "attach_simulated_annealing",
    "attach_vns",
    "attach_multi_strategy_coop",
    "attach_benchmark_harness",
    "attach_module_report",
    "attach_nsga2_engineering",
    "attach_ray_parallel",
]
