"""
Adapters: algorithm logic modules for ComposableSolver.

This package is the canonical home for adapter-related abstractions.
"""

from .algorithm_adapter import AlgorithmAdapter, CompositeAdapter
from .role_adapters import RoleAdapter, MultiRoleControllerAdapter
from .vns import VNSAdapter, VNSConfig
from .moead import MOEADAdapter, MOEADConfig
from .simulated_annealing import SimulatedAnnealingAdapter, SAConfig
from .multi_strategy import MultiStrategyControllerAdapter, MultiStrategyConfig, StrategySpec, RoleSpec
from .astar import AStarAdapter, AStarConfig
from .moa_star import MOAStarAdapter, MOAStarConfig
from .trust_region_dfo import TrustRegionDFOAdapter, TrustRegionDFOConfig
from .trust_region_mo_dfo import TrustRegionMODFOAdapter, TrustRegionMODFOConfig
from .trust_region_subspace import TrustRegionSubspaceAdapter, TrustRegionSubspaceConfig
from .trust_region_nonsmooth import TrustRegionNonSmoothAdapter, TrustRegionNonSmoothConfig
from .mas import MASAdapter, MASConfig

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
    "AStarAdapter",
    "AStarConfig",
    "MOAStarAdapter",
    "MOAStarConfig",
    "TrustRegionDFOAdapter",
    "TrustRegionDFOConfig",
    "TrustRegionMODFOAdapter",
    "TrustRegionMODFOConfig",
    "TrustRegionSubspaceAdapter",
    "TrustRegionSubspaceConfig",
    "TrustRegionNonSmoothAdapter",
    "TrustRegionNonSmoothConfig",
    "MASAdapter",
    "MASConfig",
]
