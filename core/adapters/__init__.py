"""
Adapters: algorithm logic modules for ComposableSolver.

This package is the canonical home for adapter-related abstractions.
Legacy import paths in `core/algorithm_adapter.py` and `core/role_adapters.py`
re-export these symbols for backward compatibility.
"""

from .algorithm_adapter import AlgorithmAdapter, CompositeAdapter
from .role_adapters import RoleAdapter, MultiRoleControllerAdapter
from .vns import VNSAdapter, VNSConfig
from .moead import MOEADAdapter, MOEADConfig
from .simulated_annealing import SimulatedAnnealingAdapter, SAConfig
from .multi_strategy import MultiStrategyControllerAdapter, MultiStrategyConfig, StrategySpec, RoleSpec

__all__ = [
    "AlgorithmAdapter",
    "CompositeAdapter",
    "RoleAdapter",
    "MultiRoleControllerAdapter",
    "VNSAdapter",
    "VNSConfig",
    "MOEADAdapter",
    "MOEADConfig",
    "SimulatedAnnealingAdapter",
    "SAConfig",
    "MultiStrategyControllerAdapter",
    "MultiStrategyConfig",
    "StrategySpec",
    "RoleSpec",
]
