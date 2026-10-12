"""
Adapters: algorithm logic modules for ComposableSolver.

This package is the canonical home for adapter-related abstractions.
"""

from .algorithm_adapter import (
    AdapterCommitEvidence,
    AdapterCommitIssue,
    AdapterCommitReport,
    AdapterRollbackError,
    AdapterStepTransaction,
    AlgorithmAdapter,
    CompositeAdapter,
    PopulationPartition,
)
from .candidate_proposer import CandidateProposerAdapter
from .proposal_repair import ProposalRepair
from .unit_backed import UnitBackedAdapter, UnitField
from .role_adapters import RoleAdapter, RoleRouterAdapter
from .vns import VNSAdapter, VNSConfig
from .moead import MOEADAdapter, MOEADConfig
from .simulated_annealing import SimulatedAnnealingAdapter, SAConfig
from .strategy_task import StrategyTask, StrategyOrigin
from .multi_strategy import (
    StrategyRouterAdapter,
    MultiStrategyConfig,
    MultiStrategyControlRule,
    StrategySpec,
    StrategyInstanceSpec,
    RoleSpec,
)
from .serial_strategy import StrategyChainAdapter, SerialStrategyConfig, SerialPhaseSpec
from .astar import AStarAdapter, AStarConfig
from .moa_star import MOAStarAdapter, MOAStarConfig
from .trust_region_dfo import TrustRegionDFOAdapter, TrustRegionDFOConfig
from .trust_region_mo_dfo import TrustRegionMODFOAdapter, TrustRegionMODFOConfig
from .trust_region_subspace import TrustRegionSubspaceAdapter, TrustRegionSubspaceConfig
from .trust_region_nonsmooth import TrustRegionNonSmoothAdapter, TrustRegionNonSmoothConfig
from .mas import MASAdapter, MASConfig
from .async_event_driven import AsyncEventDrivenAdapter, AsyncEventDrivenConfig, EventCaseSpec, EventStrategySpec
from .single_trajectory_adaptive import SingleTrajectoryAdaptiveAdapter, SingleTrajectoryAdaptiveConfig
from .differential_evolution import DifferentialEvolutionAdapter, DEConfig
from .gradient_descent import GradientDescentAdapter, GradientDescentConfig
from .gradient_optimizer import GradientOptimizerAdapter, GradientOptimizerConfig
from .gaussian_search import GaussianSearchAdapter, GaussianSearchConfig
from .fixed_candidate import FixedCandidateAdapter
from .elite_retention import EliteRetentionAdapter, EliteRetentionConfig
from .pattern_search import PatternSearchAdapter, PatternSearchConfig
from .nsga2 import NSGA2Adapter, NSGA2Config
from .nsga3 import NSGA3Adapter, NSGA3Config
from .spea2 import SPEA2Adapter, SPEA2Config

__all__ = [
    "ProposalRepair",
    "CandidateProposerAdapter", "UnitBackedAdapter", "UnitField", "StrategyInstanceSpec",
    "AlgorithmAdapter",
    "AdapterCommitEvidence",
    "AdapterCommitIssue",
    "AdapterCommitReport",
    "AdapterStepTransaction",
    "AdapterRollbackError",
    "CompositeAdapter",
    "PopulationPartition",
    "RoleAdapter",
    "RoleRouterAdapter",
    "VNSAdapter",
    "VNSConfig",
    "MOEADAdapter",
    "MOEADConfig",
    "SimulatedAnnealingAdapter",
    "SAConfig",
    "StrategyRouterAdapter",
    "StrategyTask",
    "StrategyOrigin",
    "MultiStrategyConfig",
    "MultiStrategyControlRule",
    "StrategySpec",
    "RoleSpec",
    "StrategyChainAdapter",
    "SerialStrategyConfig",
    "SerialPhaseSpec",
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
    "AsyncEventDrivenAdapter",
    "AsyncEventDrivenConfig",
    "EventCaseSpec",
    "EventStrategySpec",
    "SingleTrajectoryAdaptiveAdapter",
    "SingleTrajectoryAdaptiveConfig",
    "DifferentialEvolutionAdapter",
    "DEConfig",
    "GradientDescentAdapter",
    "GradientDescentConfig",
    "GradientOptimizerAdapter",
    "GradientOptimizerConfig",
    "GaussianSearchAdapter",
    "GaussianSearchConfig",
    "FixedCandidateAdapter",
    "EliteRetentionAdapter",
    "EliteRetentionConfig",
    "PatternSearchAdapter",
    "PatternSearchConfig",
    "NSGA2Adapter",
    "NSGA2Config",
    "NSGA3Adapter",
    "NSGA3Config",
    "SPEA2Adapter",
    "SPEA2Config",
]
