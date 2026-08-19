"""Core modules exposed by NSGABlack."""

from __future__ import annotations

from .acceleration import (
    AccelerationError,
    AccelerationFacade,
    AccelerationRegistry,
    AsyncHandle,
    ExecutionResult,
    GpuBackend,
    ProcessPoolBackend,
    ThreadPoolBackend,
)
from .acceleration_helpers import maybe_accel_map, maybe_accel_run
from .base import BlackBoxProblem
from .blank_solver import SolverBase
from .composable_solver import ComposableSolver
from .control_plane import (
    BaseController,
    BudgetController,
    ControlArbiter,
    ControlDecision,
    EvaluationBudgetExceeded,
    RuntimeController,
    StopController,
)
from .evolution_solver import EvolutionSolver
from .evaluation_runtime import (
    EvaluationMediator,
    EvaluationMediatorConfig,
    EvaluationProvider,
    EvaluationProviderContractError,
    IndividualEvaluationResult,
    PopulationEvaluationResult,
)
from .evaluation_feedback import AdapterFeedback, OptimizationFeedbackBatch
from .nested_solver import (
    CaseInnerRuntimeEvaluator,
    ChildCaseExecutionError,
    InnerRuntimeConfig,
    InnerRuntimeEvaluator,
    InnerSolveRequest,
    InnerSolveResult,
    TaskInnerRuntimeEvaluator,
)
from .solver_result import DEFAULT_CASE_RESULT_INLINE_MAX_BYTES, build_solver_result
from .state.incumbent import CandidateProvenance, IncumbentState, ScalarizationError
from blackbase.types import SolveQuality, SolverResult
from ..adapters import AlgorithmAdapter, CompositeAdapter, RoleAdapter, RoleRouterAdapter
from .interfaces import (
    BiasInterface,
    PluginInterface,
    OptimizationContext,
    RepresentationInterface,
    VisualizationInterface,
    create_bias_context,
    has_bias_module,
    has_numba,
    has_representation_module,
    has_visualization_module,
    load_bias_module,
    load_representation_pipeline,
)

__all__ = [
    "BlackBoxProblem",
    "EvolutionSolver",
    "SolverBase",
    "AccelerationRegistry",
    "AccelerationFacade",
    "ExecutionResult",
    "AccelerationError",
    "AsyncHandle",
    "ThreadPoolBackend",
    "ProcessPoolBackend",
    "GpuBackend",
    "maybe_accel_run",
    "maybe_accel_map",
    "AlgorithmAdapter",
    "CompositeAdapter",
    "ComposableSolver",
    "RoleAdapter",
    "RoleRouterAdapter",
    "BiasInterface",
    "RepresentationInterface",
    "VisualizationInterface",
    "PluginInterface",
    "BaseController",
    "BudgetController",
    "ControlDecision",
    "ControlArbiter",
    "EvaluationBudgetExceeded",
    "RuntimeController",
    "StopController",
    "EvaluationMediator",
    "EvaluationMediatorConfig",
    "EvaluationProvider",
    "EvaluationProviderContractError",
    "IndividualEvaluationResult",
    "PopulationEvaluationResult",
    "AdapterFeedback",
    "OptimizationFeedbackBatch",
    "InnerSolveRequest",
    "InnerSolveResult",
    "CaseInnerRuntimeEvaluator",
    "ChildCaseExecutionError",
    "InnerRuntimeEvaluator",
    "TaskInnerRuntimeEvaluator",
    "InnerRuntimeConfig",
    "SolverResult",
    "SolveQuality",
    "DEFAULT_CASE_RESULT_INLINE_MAX_BYTES",
    "build_solver_result",
    "IncumbentState",
    "CandidateProvenance",
    "ScalarizationError",
    "OptimizationContext",
    "has_bias_module",
    "has_representation_module",
    "has_visualization_module",
    "has_numba",
    "load_bias_module",
    "load_representation_pipeline",
    "create_bias_context",
]
