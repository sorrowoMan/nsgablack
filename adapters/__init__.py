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
from .pool_search import PoolSearchAdapter, PoolSearchSpec
from .pool_tasks import PoolTaskAdapter, PoolTaskSpec
from .subpools import subpools, SubpoolSelection
from .unit_backed import UnitBackedAdapter, UnitField
from .parent_selection import ParentSelectionRequest, MixedPoolParentSelector
from .selection import SelectionRequest, FeasibilityFirstSelection
from .change import ChangeRequest
from .change_pool import ChangeResult, PoolEdit, PoolOutput, Pool
from .pool_partition import partition
from .change_batch import ChangeBatchResult
from .pool_maintenance import PoolMaintenanceRequest
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
from .search_plan import SearchPlanAdapter, SearchProgress, ExecutionPlan, stage, serial, multi, repeat
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
from .bayesian_optimization import (
    BayesianOptimizationAdapter, BayesianOptimizationConfig, FixedRBFConfig,
    FixedRBFPosterior, LowerConfidenceBound, GridAcquisitionOptimizer,
)
from .cmaes import CMAESAdapter, CMAParameters, GaussianCohortSampler, PositiveCMAUpdate, StableObjectiveRanking
from .map_elites import MapElitesAdapter, MapElitesConfig, IdentityDescriptor, GridCells, MinimizeObjective, SequenceEmitter, GaussianArchiveEmitter

__all__ = [
    "BayesianOptimizationAdapter", "BayesianOptimizationConfig", "FixedRBFConfig",
    "FixedRBFPosterior", "LowerConfidenceBound", "GridAcquisitionOptimizer",
    "CMAESAdapter", "CMAParameters", "GaussianCohortSampler", "PositiveCMAUpdate", "StableObjectiveRanking",
    "MapElitesAdapter", "MapElitesConfig", "IdentityDescriptor", "GridCells", "MinimizeObjective", "SequenceEmitter", "GaussianArchiveEmitter",
    "SearchPlanAdapter", "SearchProgress", "ExecutionPlan", "stage", "serial", "multi", "repeat",
    "PoolSearchAdapter", "PoolSearchSpec",
    "PoolTaskAdapter", "PoolTaskSpec",
    "subpools", "SubpoolSelection",
    "ProposalRepair",
    "CandidateProposerAdapter", "UnitBackedAdapter", "UnitField", "StrategyInstanceSpec",
    "AlgorithmAdapter",
    "ParentSelectionRequest",
    "MixedPoolParentSelector",
    "SelectionRequest",
    "ChangeRequest",
    "ChangeResult",
    "ChangeBatchResult",
    "Pool",
    "partition",
    "PoolMaintenanceRequest",
    "PoolEdit",
    "PoolOutput",
    "FeasibilityFirstSelection",
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
